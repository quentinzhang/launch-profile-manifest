#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


TASK_SCHEMA_URL = (
    "https://quentinzhang.github.io/launch-profile-manifest/"
    "spec/browser-task/v0.1/browser-task.schema.json"
)
SITE_PROFILE_SCHEMA_URL = (
    "https://quentinzhang.github.io/launch-profile-manifest/"
    "spec/browser-task/v0.1/site-target-profile.schema.json"
)
SKILL_SOURCE = (
    "https://github.com/quentinzhang/launch-profile-manifest/"
    "tree/main/skills/directory-submission"
)


DEFAULT_ADDON_PATH = os.environ.get("CONSOLEX_ADDON_PATH", "/private/var/www/consolex_addon")

PRODUCT_FIELD_KEYS = {
    "productName",
    "companyName",
    "websiteUrl",
    "tagline",
    "shortDescription",
    "longDescription",
    "categories",
    "pricing",
    "tags",
    "contactEmail",
    "founderName",
    "logoUrl",
    "screenshotUrls",
    "demoVideoUrl",
    "twitterUrl",
    "linkedinUrl",
}
URL_FIELD_KEYS = {"websiteUrl", "logoUrl", "demoVideoUrl", "twitterUrl", "linkedinUrl"}
EVIDENCE_STATUSES = {"explicit", "derived", "inferred"}


def run_agent_inbox_add(document_path: Path, source_agent: str, source_task_id: str | None, addon_path: Path) -> dict[str, Any]:
    command = [
        "npm",
        "--prefix",
        str(addon_path),
        "run",
        "agent-inbox",
        "--",
        "add",
        str(document_path),
        "--source",
        source_agent,
    ]
    if source_task_id:
        command.extend(["--source-task-id", source_task_id])

    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(addon_path.parent),
    )
    stdout = (process.stdout or "").strip()
    stderr = (process.stderr or "").strip()
    if process.returncode != 0:
        raise RuntimeError(
            "agent-inbox add failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        )

    parsed = extract_tail_json(stdout)
    if parsed is not None:
        return parsed
    return {"ok": True, "deliveryRaw": stdout}


def extract_tail_json(text: str) -> dict[str, Any] | None:
    """Try decoding a JSON payload from the tail of stdout text."""
    body = text.strip()
    for index in range(len(body) - 1, -1, -1):
        if body[index] != "{":
            continue
        try:
            return json.loads(body[index:])
        except json.JSONDecodeError:
            continue
    return None


def detect_transport_for_route(route: str, addon_path: Path | None) -> str:
    if route == "consolex-web":
        return "consolex-web"
    if route == "agent-inbox":
        return "agent-inbox"
    if addon_path is None:
        return "consolex-web"
    return "agent-inbox"


def shell_envelope(task: dict[str, Any], route: str) -> dict[str, Any]:
    if route == "consolex-web":
        return {
            "action": "sync_submission_task",
            "payload": {"task": task},
        }
    return task


SITE_PROFILE_KEYS = {
    "$schema",
    "profileVersion",
    "id",
    "name",
    "hosts",
    "submissionUrl",
    "homepageUrl",
    "channelType",
    "bestFit",
    "submissionAccess",
    "submissionPricing",
    "requiresLogin",
    "submissionNote",
    "requiredAssets",
    "manualFields",
    "manualSteps",
    "autofillTrigger",
    "requiredAutofillFields",
    "fieldMappingStatus",
    "fieldMappingVerifiedAt",
    "fieldSelectors",
    "fieldHints",
    "autofillUrlPatterns",
    "source",
    "extensions",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def localized(value: Any, preferred: str) -> str:
    if not isinstance(value, dict):
        return ""
    for key in (preferred, preferred.split("-", 1)[0], "en"):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    for text in value.values():
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def description(product: dict[str, Any], preferred: str, length: str) -> str:
    descriptions = product.get("descriptions")
    if not isinstance(descriptions, dict):
        return ""
    for key in (preferred, preferred.split("-", 1)[0], "en"):
        value = descriptions.get(key)
        if isinstance(value, dict) and isinstance(value.get(length), str):
            return value[length].strip()
    for value in descriptions.values():
        if isinstance(value, dict) and isinstance(value.get(length), str):
            return value[length].strip()
    return ""


def first_asset(profile: dict[str, Any], role: str) -> str:
    for asset in profile.get("assets", []):
        if isinstance(asset, dict) and asset.get("role") == role:
            url = asset.get("url")
            if isinstance(url, str):
                return url
    return ""


def social_url(product: dict[str, Any], hosts: set[str]) -> str:
    for value in product.get("socialLinks", []):
        if not isinstance(value, str):
            continue
        host = (urlparse(value).hostname or "").lower()
        if host in hosts or any(host.endswith(f".{item}") for item in hosts):
            return value
    return ""


def pricing(product: dict[str, Any]) -> str:
    rendered = []
    for offer in product.get("offers", []):
        if not isinstance(offer, dict):
            continue
        parts = [str(offer.get("name", "")).strip()]
        if isinstance(offer.get("price"), (int, float)):
            parts.append(str(offer["price"]))
            if offer.get("currency"):
                parts.append(str(offer["currency"]))
        if offer.get("billingPeriod"):
            parts.append(f"/ {offer['billingPeriod']}")
        text = " ".join(part for part in parts if part)
        if text:
            rendered.append(text)
    return "; ".join(rendered)


def text_list(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return ""


def consolex_extension(profile: dict[str, Any]) -> dict[str, Any]:
    extensions = profile.get("extensions")
    if not isinstance(extensions, dict):
        return {}
    value = extensions.get("ai.consolex")
    return value if isinstance(value, dict) else {}


def product_values(profile: dict[str, Any], preferred: str) -> dict[str, str]:
    product = profile.get("product")
    if not isinstance(product, dict):
        raise ValueError("profile.product must be an object")
    screenshots = [
        asset.get("url")
        for asset in profile.get("assets", [])
        if isinstance(asset, dict) and asset.get("role") == "screenshot" and isinstance(asset.get("url"), str)
    ]
    def clean(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    extension = consolex_extension(profile)
    values = {
        "productName": clean(product.get("name")),
        "companyName": clean(extension.get("companyName")),
        "websiteUrl": clean(product.get("canonicalUrl")),
        "tagline": localized(product.get("tagline"), preferred),
        "shortDescription": description(product, preferred, "short"),
        "longDescription": description(product, preferred, "long"),
        "categories": ", ".join(str(item) for item in product.get("categories", []) if str(item).strip()),
        "pricing": clean(extension.get("pricingSummary")) or pricing(product),
        "tags": text_list(extension.get("tags")),
        "contactEmail": clean(extension.get("contactEmail")),
        "founderName": clean(extension.get("founderName")),
        "logoUrl": first_asset(profile, "logo") or first_asset(profile, "icon"),
        "screenshotUrls": "\n".join(screenshots),
        "demoVideoUrl": first_asset(profile, "demo_video"),
        "twitterUrl": social_url(product, {"x.com", "twitter.com"}),
        "linkedinUrl": social_url(product, {"linkedin.com"}),
    }
    return {key: value for key, value in values.items() if value}


def validate_product_values(values: Any) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValueError("productProfile must be an object")
    unknown = sorted(set(values) - PRODUCT_FIELD_KEYS)
    if unknown:
        raise ValueError(f"productProfile contains unsupported field(s): {', '.join(unknown)}")

    cleaned: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"productProfile.{key} must be a string")
        text = value.strip()
        if not text:
            continue
        if len(text) > 5000:
            raise ValueError(f"productProfile.{key} exceeds 5000 characters")
        cleaned[key] = text

    for key in URL_FIELD_KEYS:
        value = cleaned.get(key)
        if value and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError(f"productProfile.{key} must be an HTTP(S) URL")
    screenshots = cleaned.get("screenshotUrls", "")
    for value in screenshots.splitlines():
        if value.strip() and urlparse(value.strip()).scheme not in {"http", "https"}:
            raise ValueError("every productProfile.screenshotUrls entry must be an HTTP(S) URL")
    email = cleaned.get("contactEmail")
    if email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        raise ValueError("productProfile.contactEmail must be an email address")
    return cleaned


def direct_product_values(document: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    if document.get("confirmedByUser") is not True:
        raise ValueError("local Product Profile must be reviewed with confirmedByUser set to true")

    wrapped = "productProfile" in document
    if wrapped:
        allowed = {"confirmedByUser", "inputType", "source", "productProfile", "fieldEvidence"}
        unknown = sorted(set(document) - allowed)
        if unknown:
            raise ValueError(
                "local Product Profile packet contains unsupported top-level field(s): " + ", ".join(unknown)
            )
    raw_values = document.get("productProfile") if wrapped else {
        key: value for key, value in document.items() if key in PRODUCT_FIELD_KEYS
    }
    if not wrapped:
        allowed = PRODUCT_FIELD_KEYS | {"confirmedByUser", "inputType", "source", "fieldEvidence"}
        unknown = sorted(set(document) - allowed)
        if unknown:
            raise ValueError(
                "local Product Profile contains unsupported top-level field(s): " + ", ".join(unknown)
            )
    values = validate_product_values(raw_values)

    input_type = document.get("inputType", "structured")
    if input_type not in {"structured", "unstructured"}:
        raise ValueError("inputType must be structured or unstructured")
    evidence = document.get("fieldEvidence")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("fieldEvidence must be an object")
    if input_type == "unstructured":
        if not isinstance(evidence, dict):
            raise ValueError("unstructured input requires fieldEvidence")
        missing_evidence = sorted(set(values) - set(evidence))
        if missing_evidence:
            raise ValueError("fieldEvidence is missing field(s): " + ", ".join(missing_evidence))

    normalized_evidence: dict[str, dict[str, Any]] = {}
    if isinstance(evidence, dict):
        unknown_evidence = sorted(set(evidence) - PRODUCT_FIELD_KEYS)
        if unknown_evidence:
            raise ValueError("fieldEvidence contains unsupported field(s): " + ", ".join(unknown_evidence))
        for key, item in evidence.items():
            if key not in values:
                raise ValueError(f"fieldEvidence.{key} has no matching populated productProfile field")
            if not isinstance(item, dict):
                raise ValueError(f"fieldEvidence.{key} must be an object")
            status = item.get("status")
            evidence_text = item.get("evidence")
            confidence = item.get("confidence")
            if status not in EVIDENCE_STATUSES:
                raise ValueError(
                    f"fieldEvidence.{key}.status must be one of: {', '.join(sorted(EVIDENCE_STATUSES))}"
                )
            if not isinstance(evidence_text, str) or not evidence_text.strip():
                raise ValueError(f"fieldEvidence.{key}.evidence must be a non-empty string")
            if confidence is not None and (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or confidence < 0
                or confidence > 1
            ):
                raise ValueError(f"fieldEvidence.{key}.confidence must be between 0 and 1")
            normalized_evidence[key] = {
                "status": status,
                **({"confidence": confidence} if confidence is not None else {}),
                "evidence": evidence_text.strip(),
            }

    metadata: dict[str, Any] = {"productProfileInput": input_type}
    source = document.get("source")
    if isinstance(source, dict):
        safe_source = {
            key: value.strip()
            for key, value in source.items()
            if key in {"type", "title"} and isinstance(value, str) and value.strip()
        }
        if safe_source:
            metadata["source"] = safe_source
    if normalized_evidence:
        metadata["fieldEvidence"] = normalized_evidence
    return values, metadata


def target_profiles(paths: list[Path]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in paths:
        document = load_object(path)
        is_catalogue = isinstance(document.get("profiles"), list)
        candidates = document["profiles"] if is_catalogue else [document]
        if is_catalogue:
            candidates = [candidate for candidate in candidates if isinstance(candidate, dict) and candidate.get("defaultSelected") is True]
            if not candidates:
                raise ValueError(f"{path} catalogue has no defaultSelected target profiles")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError(f"{path} contains a non-object target profile")
            site_profile = {key: candidate[key] for key in SITE_PROFILE_KEYS if key in candidate}
            site_profile["$schema"] = SITE_PROFILE_SCHEMA_URL
            site_profile["profileVersion"] = "0.1"
            if site_profile.get("fieldMappingStatus") == "verified_text_fields":
                site_profile["fieldMappingStatus"] = "partial"
            site_id = str(site_profile.get("id", "")).strip()
            submission_url = str(site_profile.get("submissionUrl", "")).strip()
            hosts = site_profile.get("hosts")
            if not site_id or not submission_url or not isinstance(hosts, list) or not hosts:
                raise ValueError(f"{path} target requires id, hosts, and submissionUrl")
            profiles.append(
                {
                    "targetId": site_id,
                    "siteId": site_id,
                    "submissionUrl": submission_url,
                    "status": "ready",
                    "siteProfile": site_profile,
                }
            )
    if not profiles:
        raise ValueError("at least one target profile is required")
    return profiles


def validate_required_target_fields(values: dict[str, str], targets: list[dict[str, Any]]) -> None:
    missing_by_target: list[str] = []
    for target in targets:
        site_profile = target["siteProfile"]
        required = site_profile.get("requiredAutofillFields", [])
        if not isinstance(required, list):
            continue
        missing = sorted(field for field in required if not values.get(field))
        if missing:
            missing_by_target.append(f"{target['targetId']}: {', '.join(missing)}")
    if missing_by_target:
        raise ValueError("missing required target field(s): " + "; ".join(missing_by_target))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a directory-submission Browser Task from a Launch Profile or local Product Profile"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--profile", type=Path)
    input_group.add_argument("--product-profile", type=Path)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--target", required=True, action="append", type=Path)
    parser.add_argument("--source-agent", default="compatible-agent")
    parser.add_argument("--task-id")
    parser.add_argument("--campaign-id")
    parser.add_argument("--label")
    parser.add_argument("--language", default="en")
    parser.add_argument("--transport", choices=("bare", "consolex-web"), default="bare")
    parser.add_argument("--route", choices=("auto", "consolex-web", "agent-inbox"), default="auto")
    parser.add_argument("--addon-path", type=Path, default=Path(DEFAULT_ADDON_PATH))
    parser.add_argument("--deliver", action="store_true")
    parser.add_argument("--source-task-id")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    profile = load_object(args.profile) if args.profile else None
    local_profile = load_object(args.product_profile) if args.product_profile else None
    profile_ref: dict[str, str] | None = None
    input_metadata: dict[str, Any] = {}
    if profile is not None:
        provenance = profile.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("confirmedByUser") is not True:
            raise ValueError("Launch Profile must be reviewed with provenance.confirmedByUser set to true")
        values = validate_product_values(product_values(profile, args.language))
        profile_ref = {
            "profileId": str(profile["id"]),
            "manifestVersion": str(profile.get("manifestVersion", "")),
        }
    else:
        assert local_profile is not None
        values, input_metadata = direct_product_values(local_profile)

    if args.release and profile is None:
        raise ValueError("--release requires --profile because a Release Envelope references a Launch Profile")
    release = load_object(args.release) if args.release else None
    if release and profile is not None and release.get("profileId") != profile.get("id"):
        raise ValueError("Release Envelope profileId must exactly match the Launch Profile id")

    if not values.get("productName"):
        raise ValueError("productProfile.productName is required")
    if not values.get("websiteUrl"):
        raise ValueError("productProfile.websiteUrl is required")
    task_id = args.task_id or f"directory-submission-{uuid4()}"
    targets = target_profiles(args.target)
    validate_required_target_fields(values, targets)
    target_count = len(targets)
    label = args.label or f"Submit {values['productName']} to {target_count} director{'y' if target_count == 1 else 'ies'}"
    if release and profile_ref is not None:
        profile_ref["releaseId"] = str(release["id"])

    task: dict[str, Any] = {
        "$schema": TASK_SCHEMA_URL,
        "taskVersion": "0.1",
        "taskId": task_id,
        "taskType": "directory_submission",
        "taskLabel": label,
        "sourceAgent": args.source_agent,
        "requiresConfirmation": True,
        "requestedCapabilities": ["store_task"],
        "productProfile": values,
        "targets": targets,
        "options": {"overwrite": False, "renderOverlay": True},
        "provenance": {
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator": "directory-submission reference builder",
            "skill": {"name": "directory-submission", "version": "0.2.0", "source": SKILL_SOURCE},
        },
        "extensions": {"ai.consolex": input_metadata} if input_metadata else {},
    }
    if profile_ref is not None:
        task["profileRef"] = profile_ref
    if args.campaign_id:
        task["campaignId"] = args.campaign_id

    addon_path = args.addon_path if args.addon_path and args.addon_path.exists() else None
    resolved_route = detect_transport_for_route(args.route, addon_path)

    document: dict[str, Any]
    if args.transport == "consolex-web" or resolved_route == "consolex-web":
        document = shell_envelope(task, "consolex-web")
    else:
        document = task

    # For local delivery we always enqueue the bare task shape.
    if args.deliver and resolved_route == "agent-inbox":
        document = task

    args.output.write_text(f"{json.dumps(document, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    output_shape = "consolex-web connector envelope" if "action" in document else "bare Browser Task"
    print(f"wrote {output_shape} with {len(task['targets'])} target(s) to {args.output}")
    print(f"selected route: {resolved_route}")

    if resolved_route == "consolex-web":
        envelope = shell_envelope(task, "consolex-web")
        if not args.deliver:
            print(
                '<consolex-browser-task identifier="' + task_id + '" '
                'type="application/vnd.consolex.browser-task+json" '
                f'title="{label}">'
            )
            print(json.dumps(envelope, ensure_ascii=False))
            print("</consolex-browser-task>")
            return 0

        print("ConsoleX Web delivery selected. Render this action card in-chat:\n")
        print(
            '<consolex-browser-task identifier="' + task_id + '" '
            'type="application/vnd.consolex.browser-task+json" '
            f'title="{label}">'
        )
        print(json.dumps(envelope, ensure_ascii=False))
        print("</consolex-browser-task>")
        return 0

    if args.deliver:
        if addon_path is None:
            raise RuntimeError("route set to local inbox but CONSOLEX_ADDON_PATH is missing or path does not exist")

        delivery = run_agent_inbox_add(
            document_path=args.output,
            source_agent=args.source_agent,
            source_task_id=args.source_task_id,
            addon_path=addon_path,
        )
        print(f"local inbox delivery: route={resolved_route}")
        print(json.dumps(delivery, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
