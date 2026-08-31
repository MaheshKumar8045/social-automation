from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .provider_catalog import enabled_providers, load_catalog


def _reset_seconds(item: dict[str, Any]) -> float:
    value = item.get("quota", {}).get("reset_at")
    if not value:
        return float("inf")
    try:
        return max(0.0, (datetime.fromisoformat(value.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return float("inf")


def _has_credentials(item: dict[str, Any]) -> bool:
    if not item.get("requires_api_key", True) and not item.get("credential_env"):
        return True
    env_name = item.get("credential_env") or item.get("api_key_env")
    if not env_name:
        name = str(item.get("name", ""))
        env_name = "".join("_" if not c.isalnum() else c.upper() for c in name) + "_API_KEY"
    return bool(os.getenv(env_name))


def _paid_enabled(item: dict[str, Any], policy: dict[str, Any]) -> bool:
    if item.get("billing") not in {"paid", "payg"}:
        return True
    if not policy.get("require_explicit_paid_enablement", True):
        return True
    name = str(item.get("name", ""))
    env = item.get("paid_enablement_env") or ("ENABLE_PAID_PROVIDER_" + "".join(c if c.isalnum() else "_" for c in name.upper()))
    return os.getenv(env, "").strip().lower() in {"1", "true", "yes", "on"}


def rank_providers(media_type: str, path: str | Path | None = None) -> list[dict[str, Any]]:
    catalog = load_catalog(path)
    policy = catalog.get("policy", {})
    candidates = [p for p in enabled_providers(media_type, path) if _has_credentials(p) and _paid_enabled(p, policy)]
    max_cost = policy.get("max_cost_per_job")
    if max_cost is not None:
        candidates = [p for p in candidates if float(p.get("estimated_cost_per_job", 0) or 0) <= float(max_cost)]

    def key(p: dict[str, Any]) -> tuple[Any, ...]:
        quota = p.get("quota", {})
        billing = p.get("billing", "unknown")
        free_rank = 0 if policy.get("prefer_free", True) and billing in {"free", "subscription"} else 1
        expiry = _reset_seconds(p) if policy.get("prefer_expiring_quota", True) else float("inf")
        remaining = quota.get("remaining")
        exhausted = 1 if remaining is not None and remaining <= 0 else 0
        return (exhausted, free_rank, expiry, p.get("priority", 100))

    return sorted(candidates, key=key)


def choose_provider(media_type: str, path: str | Path | None = None) -> dict[str, Any] | None:
    ranked = rank_providers(media_type, path)
    if not ranked:
        return None
    policy = load_catalog(path).get("policy", {})
    if not policy.get("allow_paid_fallback", True):
        non_paid = [p for p in ranked if p.get("billing") in {"free", "subscription"}]
        return non_paid[0] if non_paid else None
    return ranked[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose a generation provider from configurable routing and quota policy")
    parser.add_argument("media_type", choices=("image", "video", "audio"))
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    result = choose_provider(args.media_type, args.config)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
