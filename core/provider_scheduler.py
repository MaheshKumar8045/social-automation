from __future__ import annotations

import argparse
import json
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


def rank_providers(media_type: str, path: str | Path | None = None) -> list[dict[str, Any]]:
    catalog = load_catalog(path)
    policy = catalog.get("policy", {})
    candidates = enabled_providers(media_type, path)
    max_cost = policy.get("max_cost_per_job")
    if max_cost is not None:
        candidates = [p for p in candidates if p.get("estimated_cost_per_job", 0) <= max_cost]

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
