from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate_output(plan: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if plan.get("plan_status") != "ready":
        errors.append("generation plan is not ready")
    if plan.get("unknowns_must_remain_unknown") is not True:
        errors.append("plan does not preserve unknowns")
    if output.get("document_id") != plan.get("document_id"):
        errors.append("document_id mismatch")
    if output.get("scene_id") != plan.get("scene_id"):
        errors.append("scene_id mismatch")
    if output.get("provider") is None:
        errors.append("missing provider")
    return {"valid": not errors, "errors": errors}


def validate_asset_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return {"exists": p.exists(), "is_file": p.is_file(), "path": str(p)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a generation output envelope")
    parser.add_argument("plan_json")
    parser.add_argument("output_json")
    args = parser.parse_args()
    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    output = json.loads(Path(args.output_json).read_text(encoding="utf-8"))
    result = validate_output(plan, output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
