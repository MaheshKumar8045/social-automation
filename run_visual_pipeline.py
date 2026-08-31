from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

STEPS = [
    ("Visual Knowledge Bible", "core.visual_knowledge_bible"),
    ("Canonical Visual Bible", "core.canonical_visual_bible"),
    ("Visual Fact Reconciliation", "core.visual_fact_reconciler"),
    ("Visual Conflict Classification", "core.visual_conflict_classifier"),
    ("Continuity State", "core.continuity_state"),
]


def run_module(module: str, db: str, document_id: int) -> None:
    print(f"\n=== RUNNING: {module} ===")
    result = subprocess.run([sys.executable, "-m", module, db, str(document_id)], text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def scene_smoke_test(db: str, document_id: int, scene_id: int) -> dict:
    result = subprocess.run([sys.executable, "-m", "core.scene_visual_state", db, str(document_id), str(scene_id)], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"FAIL: scene visual state failed for scene {scene_id}: {result.stderr.strip()}")
    try:
        state = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: scene {scene_id} returned invalid JSON: {exc}")
    if state.get("unknowns_must_remain_unknown") is not True:
        raise SystemExit(f"FAIL: scene {scene_id} does not preserve unknowns")
    return state


def generation_smoke_test(db: str, document_id: int, scene_id: int) -> dict:
    result = subprocess.run([sys.executable, "-m", "core.generation_context", db, str(document_id), str(scene_id), "--summary"], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"FAIL: generation context failed for scene {scene_id}: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: generation context scene {scene_id} returned invalid JSON: {exc}")
    if payload.get("continuity_available") is not True:
        raise SystemExit(f"FAIL: generation context scene {scene_id} has no continuity state")
    return payload


def planner_smoke_test(db: str, document_id: int, scene_id: int) -> dict:
    result = subprocess.run([sys.executable, "-m", "core.generation_planner", db, str(document_id), str(scene_id), "--summary"], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"FAIL: generation planner failed for scene {scene_id}: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: generation planner scene {scene_id} returned invalid JSON: {exc}")
    if payload.get("plan_status") != "ready":
        raise SystemExit(f"FAIL: generation planner scene {scene_id} is not ready")
    if payload.get("unknowns_must_remain_unknown") is not True:
        raise SystemExit(f"FAIL: generation planner scene {scene_id} does not preserve unknowns")
    return payload


def validate(db: str, document_id: int) -> None:
    with sqlite3.connect(db) as con:
        checks = {}
        checks["canonical_profiles"] = con.execute("SELECT COUNT(*) FROM canonical_visual_profiles WHERE document_id=?", (document_id,)).fetchone()[0]
        checks["canonical_facts"] = con.execute("""SELECT COUNT(*) FROM canonical_visual_facts cvf JOIN canonical_visual_profiles cvp ON cvp.id=cvf.canonical_visual_profile_id WHERE cvp.document_id=?""", (document_id,)).fetchone()[0]
        checks["strong_conflicts"] = con.execute("SELECT COUNT(*) FROM visual_conflict_classification WHERE document_id=? AND classification='strong_conflict'", (document_id,)).fetchone()[0]
        checks["unsupported"] = con.execute("SELECT COUNT(*) FROM visual_fact_reconciliation WHERE document_id=? AND status='unsupported'", (document_id,)).fetchone()[0]
        checks["known_bad_phrase_facts"] = con.execute("""SELECT COUNT(*) FROM visual_facts WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=? AND profile_type='character') AND (LOWER(evidence) LIKE '%small tongue of platinum%' OR LOWER(evidence) LIKE '%large scale map%' OR LOWER(evidence) LIKE '%serious difficulty%' OR LOWER(value) LIKE '%200 feet%')""", (document_id,)).fetchone()[0]
        checks["canonical_characters"] = con.execute("SELECT COUNT(*) FROM canonical_characters WHERE document_id=? AND status IN ('confirmed','likely','singleton')", (document_id,)).fetchone()[0]
        checks["canonical_without_source_profile"] = con.execute("""SELECT COUNT(*) FROM canonical_characters cc LEFT JOIN canonical_visual_profiles cvp ON cvp.canonical_character_id=cc.id AND cvp.document_id=cc.document_id WHERE cc.document_id=? AND cc.status IN ('confirmed','likely','singleton') AND cvp.id IS NULL""", (document_id,)).fetchone()[0]
        checks["scene_context_rows"] = con.execute("SELECT COUNT(*) FROM scene_visual_context WHERE document_id=?", (document_id,)).fetchone()[0]
        checks["object_mentions"] = con.execute("SELECT COUNT(*) FROM visual_object_mentions WHERE document_id=?", (document_id,)).fetchone()[0]
        checks["continuity_rows"] = con.execute("SELECT COUNT(*) FROM visual_scene_continuity WHERE document_id=?", (document_id,)).fetchone()[0]
        checks["continuity_state_rows"] = con.execute("SELECT COUNT(*) FROM visual_entity_state WHERE document_id=?", (document_id,)).fetchone()[0]

    print("\n=== VISUAL + CONTINUITY VALIDATION ===")
    for key, value in checks.items():
        print(f"{key}: {value}")

    if checks["canonical_profiles"] != checks["canonical_characters"]:
        raise SystemExit("FAIL: canonical visual profiles do not cover the usable canonical character layer")
    if checks["canonical_facts"] == 0:
        raise SystemExit("FAIL: canonical visual fact layer is empty")
    if checks["known_bad_phrase_facts"] != 0:
        raise SystemExit("FAIL: known false-positive visual evidence remains")
    if checks["strong_conflicts"] != 0:
        raise SystemExit("FAIL: strong visual conflicts detected")
    if checks["unsupported"] != 0:
        raise SystemExit("FAIL: unsupported reconciled facts detected")
    if checks["canonical_without_source_profile"] != 0:
        raise SystemExit("FAIL: usable canonical character lacks a visual profile")
    if checks["scene_context_rows"] == 0:
        raise SystemExit("FAIL: scene visual context is empty")
    if checks["object_mentions"] == 0:
        raise SystemExit("FAIL: object mention layer is empty")
    if checks["continuity_rows"] == 0 or checks["continuity_state_rows"] == 0:
        raise SystemExit("FAIL: continuity state is empty")

    for scene_id in (1, 8, 21, 78, 200, 291):
        state = scene_smoke_test(db, document_id, scene_id)
        print(f"scene_{scene_id}: characters={len(state.get('characters', []))}")
        payload = generation_smoke_test(db, document_id, scene_id)
        print(f"generation_{scene_id}: characters={payload['characters']} visual_facts={payload['visual_fact_count']} objects={payload['objects']} events={payload['events']}")
        plan = planner_smoke_test(db, document_id, scene_id)
        print(f"planner_{scene_id}: characters={plan['characters']} visual_facts={plan['visual_fact_count']} objects={plan['objects']} events={plan['events']} evidence={plan['evidence_items']}")

    print("RESULT: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run visual, continuity, and generation-planning regression checks")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    if not Path(args.database).exists():
        raise SystemExit(f"Database not found: {args.database}")
    for _, module in STEPS:
        run_module(module, args.database, args.document_id)
    validate(args.database, args.document_id)


if __name__ == "__main__":
    main()
