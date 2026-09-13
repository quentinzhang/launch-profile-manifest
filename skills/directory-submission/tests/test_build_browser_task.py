from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
BUILDER = SKILL_ROOT / "scripts" / "build_browser_task.py"
VALIDATOR = REPO_ROOT / "skills" / "collect-launch-profile" / "scripts" / "validate_documents.py"

BUILDER_SPEC = importlib.util.spec_from_file_location("directory_submission_builder", BUILDER)
assert BUILDER_SPEC and BUILDER_SPEC.loader
BUILDER_MODULE = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER_MODULE)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def target(required_fields: list[str] | None = None) -> dict:
    value = {
        "id": "example-directory",
        "hosts": ["directory.example"],
        "submissionUrl": "https://directory.example/submit",
        "fieldMappingStatus": "verify_before_fill",
        "fieldHints": {
            "productName": ["product name"],
            "websiteUrl": ["website"],
        },
    }
    if required_fields is not None:
        value["requiredAutofillFields"] = required_fields
    return value


class BuildBrowserTaskTests(unittest.TestCase):
    def run_builder(self, product: dict, site: dict) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            product_path = root / "product.json"
            target_path = root / "target.json"
            output_path = root / "task.json"
            write_json(product_path, product)
            write_json(target_path, site)
            process = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--product-profile",
                    str(product_path),
                    "--target",
                    str(target_path),
                    "--route",
                    "agent-inbox",
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            output = json.loads(output_path.read_text()) if output_path.exists() else None
            if process.returncode == 0:
                validation = subprocess.run(
                    [sys.executable, str(VALIDATOR), "--browser-task", str(output_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            return process, output

    def test_unstructured_packet_preserves_values_and_evidence(self) -> None:
        product_profile = {
            "productName": "Atlas",
            "companyName": "Atlas Labs",
            "websiteUrl": "https://example.com/atlas",
            "shortDescription": "A reviewed product description.",
            "categories": "AI Tools, Productivity",
            "contactEmail": "founder@example.com",
            "founderName": "Quentin",
        }
        evidence = {
            field: {
                "status": "derived" if field in {"shortDescription", "categories"} else "explicit",
                "confidence": 0.9,
                "evidence": f"Reviewed source for {field}.",
            }
            for field in product_profile
        }
        packet = {
            "inputType": "unstructured",
            "confirmedByUser": True,
            "source": {"type": "user_document", "title": "Product notes"},
            "productProfile": product_profile,
            "fieldEvidence": evidence,
        }

        process, task = self.run_builder(
            packet,
            target(["productName", "websiteUrl", "contactEmail", "founderName"]),
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        assert task is not None
        self.assertEqual(task["productProfile"], product_profile)
        self.assertNotIn("profileRef", task)
        metadata = task["extensions"]["ai.consolex"]
        self.assertEqual(metadata["productProfileInput"], "unstructured")
        self.assertEqual(metadata["fieldEvidence"]["categories"]["status"], "derived")
        self.assertEqual(task["provenance"]["skill"]["version"], "0.2.1")

    def test_unstructured_packet_requires_evidence_for_every_value(self) -> None:
        packet = {
            "inputType": "unstructured",
            "confirmedByUser": True,
            "productProfile": {
                "productName": "Atlas",
                "websiteUrl": "https://example.com/atlas",
            },
            "fieldEvidence": {
                "productName": {
                    "status": "explicit",
                    "evidence": "The product is Atlas.",
                }
            },
        }

        process, task = self.run_builder(packet, target())

        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(task)
        self.assertIn("fieldEvidence is missing field(s): websiteUrl", process.stderr)

    def test_target_required_fields_fail_before_task_creation(self) -> None:
        packet = {
            "confirmedByUser": True,
            "productProfile": {
                "productName": "Atlas",
                "websiteUrl": "https://example.com/atlas",
            },
        }

        process, task = self.run_builder(packet, target(["productName", "contactEmail"]))

        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(task)
        self.assertIn("example-directory: contactEmail", process.stderr)

    def test_launch_profile_consolex_extension_maps_all_directory_fields(self) -> None:
        profile = json.loads((REPO_ROOT / "examples" / "saas-profile.json").read_text())
        profile["extensions"] = {
            "ai.consolex": {
                "companyName": "Example Labs",
                "pricingSummary": "Free",
                "tags": ["launch", "productivity"],
                "contactEmail": "founder@example.com",
                "founderName": "Example Founder",
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = root / "profile.json"
            target_path = root / "target.json"
            output_path = root / "task.json"
            write_json(profile_path, profile)
            write_json(target_path, target())
            process = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--profile",
                    str(profile_path),
                    "--target",
                    str(target_path),
                    "--route",
                    "agent-inbox",
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            task = json.loads(output_path.read_text())

        values = task["productProfile"]
        self.assertEqual(values["companyName"], "Example Labs")
        self.assertEqual(values["pricing"], "Free")
        self.assertEqual(values["tags"], "launch, productivity")
        self.assertEqual(values["contactEmail"], "founder@example.com")
        self.assertEqual(values["founderName"], "Example Founder")

    def test_local_delivery_requires_connected_sidekick_before_add(self) -> None:
        status_result = subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout='{"ok":true,"ready":false,"state":"stale","note":"Reload Sidekick."}',
            stderr="",
        )

        with patch.object(BUILDER_MODULE.subprocess, "run", return_value=status_result) as run:
            with self.assertRaisesRegex(RuntimeError, "Browser Task was generated but not queued"):
                BUILDER_MODULE.run_agent_inbox_add(
                    Path("/tmp/browser-task.json"),
                    "codex",
                    None,
                    Path("/tmp/consolex_addon"),
                )

        self.assertEqual(run.call_count, 1)
        self.assertIn("status", run.call_args.args[0])
        self.assertIn("--require-connected", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
