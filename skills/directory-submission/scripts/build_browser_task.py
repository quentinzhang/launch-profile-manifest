#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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

    values = {
        "productName": clean(product.get("name")),
        "websiteUrl": clean(product.get("canonicalUrl")),
        "tagline": localized(product.get("tagline"), preferred),
        "shortDescription": description(product, preferred, "short"),
        "longDescription": description(product, preferred, "long"),
        "categories": ", ".join(str(item) for item in product.get("categories", []) if str(item).strip()),
        "pricing": pricing(product),
        "logoUrl": first_asset(profile, "logo") or first_asset(profile, "icon"),
        "screenshotUrls": "\n".join(screenshots),
        "demoVideoUrl": first_asset(profile, "demo_video"),
        "twitterUrl": social_url(product, {"x.com", "twitter.com"}),
        "linkedinUrl": social_url(product, {"linkedin.com"}),
    }
    return {key: value for key, value in values.items() if value}


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a directory-submission Browser Task from LPM")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--target", required=True, action="append", type=Path)
    parser.add_argument("--source-agent", default="compatible-agent")
    parser.add_argument("--task-id")
    parser.add_argument("--campaign-id")
    parser.add_argument("--label")
    parser.add_argument("--language", default="en")
    parser.add_argument("--transport", choices=("bare", "consolex-web"), default="bare")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    profile = load_object(args.profile)
    provenance = profile.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("confirmedByUser") is not True:
        raise ValueError("Launch Profile must be reviewed with provenance.confirmedByUser set to true")

    release = load_object(args.release) if args.release else None
    if release and release.get("profileId") != profile.get("id"):
        raise ValueError("Release Envelope profileId must exactly match the Launch Profile id")

    values = product_values(profile, args.language)
    if not values.get("productName"):
        raise ValueError("Launch Profile product.name is required")
    task_id = args.task_id or f"directory-submission-{uuid4()}"
    targets = target_profiles(args.target)
    target_count = len(targets)
    label = args.label or f"Submit {values['productName']} to {target_count} director{'y' if target_count == 1 else 'ies'}"
    profile_ref: dict[str, str] = {
        "profileId": str(profile["id"]),
        "manifestVersion": str(profile.get("manifestVersion", "")),
    }
    if release:
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
        "profileRef": profile_ref,
        "productProfile": values,
        "targets": targets,
        "options": {"overwrite": False, "renderOverlay": True},
        "provenance": {
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator": "directory-submission reference builder",
            "skill": {"name": "directory-submission", "version": "0.1.0", "source": SKILL_SOURCE},
        },
        "extensions": {},
    }
    if args.campaign_id:
        task["campaignId"] = args.campaign_id

    document: dict[str, Any]
    if args.transport == "consolex-web":
        document = {"action": "sync_submission_task", "payload": {"task": task}}
    else:
        document = task
    args.output.write_text(f"{json.dumps(document, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"wrote {args.transport} Browser Task with {len(task['targets'])} target(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
