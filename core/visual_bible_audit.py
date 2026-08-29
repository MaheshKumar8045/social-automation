from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from statistics import mean
from typing import Any


class VisualBibleAudit:
    """Audit source-grounded visual data without changing the source data."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def run(self, document_id: int, sample_size: int = 10) -> dict[str, Any]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            report: dict[str, Any] = {"document_id": document_id}
            report["coverage"] = self._coverage(con, document_id)
            report["entity_distribution"] = self._entity_distribution(con, document_id)
            report["fact_quality"] = self._fact_quality(con, document_id)
            report["continuity"] = self._continuity(con, document_id)
            report["noise"] = self._noise(con, document_id, sample_size)
            report["samples"] = self._samples(con, document_id, sample_size)
            report["generation_readiness"] = self._readiness(report)
            return report

    @staticmethod
    def _coverage(con: sqlite3.Connection, document_id: int) -> dict[str, int]:
        def count(table: str) -> int:
            return int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE document_id=?", (document_id,)).fetchone()[0])

        scenes = count("scenes")
        contexts = count("scene_visual_context")
        profiles = count("visual_profiles")
        facts = int(con.execute("SELECT COUNT(*) FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id WHERE vp.document_id=?", (document_id,)).fetchone()[0])
        objects = count("visual_objects")
        object_mentions = count("visual_object_mentions")
        evidence_facts = int(con.execute("SELECT COUNT(*) FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id WHERE vp.document_id=? AND TRIM(vf.evidence)<>''", (document_id,)).fetchone()[0])
        return {
            "scenes": scenes,
            "scene_contexts": contexts,
            "scene_context_coverage_pct": round((contexts / scenes * 100) if scenes else 0, 2),
            "visual_profiles": profiles,
            "visual_facts": facts,
            "facts_with_evidence": evidence_facts,
            "fact_evidence_coverage_pct": round((evidence_facts / facts * 100) if facts else 0, 2),
            "visual_objects": objects,
            "object_mentions": object_mentions,
        }

    @staticmethod
    def _entity_distribution(con: sqlite3.Connection, document_id: int) -> dict[str, int]:
        rows = con.execute("SELECT profile_type, COUNT(*) n FROM visual_profiles WHERE document_id=? GROUP BY profile_type ORDER BY profile_type", (document_id,)).fetchall()
        return {str(r["profile_type"]): int(r["n"]) for r in rows}

    @staticmethod
    def _fact_quality(con: sqlite3.Connection, document_id: int) -> dict[str, Any]:
        rows = con.execute("""SELECT vf.category, COUNT(*) n, AVG(vf.confidence) avg_conf,
                                    SUM(CASE WHEN TRIM(vf.evidence)<>'' THEN 1 ELSE 0 END) evidence_n
                             FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id
                             WHERE vp.document_id=? GROUP BY vf.category ORDER BY vf.category""", (document_id,)).fetchall()
        by_category = {}
        confidences = []
        for r in rows:
            avg_conf = float(r["avg_conf"] or 0)
            confidences.append(avg_conf)
            by_category[str(r["category"])] = {"count": int(r["n"]), "avg_confidence": round(avg_conf, 3), "with_evidence": int(r["evidence_n"])}
        return {"categories": by_category, "mean_category_confidence": round(mean(confidences), 3) if confidences else 0}

    @staticmethod
    def _continuity(con: sqlite3.Connection, document_id: int) -> dict[str, Any]:
        scenes = int(con.execute("SELECT COUNT(*) FROM scenes WHERE document_id=?", (document_id,)).fetchone()[0])
        with_chars = int(con.execute("SELECT COUNT(*) FROM scene_visual_context WHERE document_id=? AND character_profile_ids<>'[]'", (document_id,)).fetchone()[0])
        with_env = int(con.execute("SELECT COUNT(*) FROM scene_visual_context WHERE document_id=? AND environment_profile_ids<>'[]'", (document_id,)).fetchone()[0])
        with_objects = int(con.execute("SELECT COUNT(*) FROM scene_visual_context WHERE document_id=? AND object_mentions<>'[]'", (document_id,)).fetchone()[0])
        recurring = int(con.execute("""SELECT COUNT(*) FROM (
            SELECT vp.id FROM visual_profiles vp
            JOIN visual_facts vf ON vf.profile_id=vp.id
            WHERE vp.document_id=? AND vp.profile_type='character' AND vf.scene_id IS NOT NULL
            GROUP BY vp.id HAVING COUNT(DISTINCT vf.scene_id) > 1
        )""", (document_id,)).fetchone()[0])
        return {
            "scenes_with_characters": with_chars,
            "scenes_with_environments": with_env,
            "scenes_with_objects": with_objects,
            "character_scene_coverage_pct": round((with_chars / scenes * 100) if scenes else 0, 2),
            "environment_scene_coverage_pct": round((with_env / scenes * 100) if scenes else 0, 2),
            "object_scene_coverage_pct": round((with_objects / scenes * 100) if scenes else 0, 2),
            "recurring_character_profiles_with_multi_scene_facts": recurring,
        }

    @staticmethod
    def _noise(con: sqlite3.Connection, document_id: int, sample_size: int) -> dict[str, Any]:
        suspicious = con.execute("""SELECT id, canonical_name, confidence, discovery_method
                                    FROM visual_profiles
                                    WHERE document_id=? AND profile_type='character'
                                      AND (canonical_name LIKE '% % % %' OR LENGTH(canonical_name)>45 OR confidence<0.5)
                                    ORDER BY confidence ASC, LENGTH(canonical_name) DESC, id
                                    LIMIT ?""", (document_id, sample_size)).fetchall()
        duplicate_norm = con.execute("""SELECT LOWER(REPLACE(REPLACE(canonical_name,'.',''),'  ',' ')) normalized, COUNT(*) n
                                        FROM visual_profiles WHERE document_id=? AND profile_type='character'
                                        GROUP BY normalized HAVING COUNT(*)>1 ORDER BY n DESC LIMIT ?""", (document_id, sample_size)).fetchall()
        return {
            "suspicious_character_sample": [dict(r) for r in suspicious],
            "duplicate_normalized_character_groups": [{"normalized": r[0], "count": int(r[1])} for r in duplicate_norm],
        }

    @staticmethod
    def _samples(con: sqlite3.Connection, document_id: int, sample_size: int) -> dict[str, Any]:
        profiles = con.execute("""SELECT id, profile_type, canonical_name, confidence
                                 FROM visual_profiles WHERE document_id=?
                                 ORDER BY confidence DESC, id LIMIT ?""", (document_id, sample_size)).fetchall()
        facts = con.execute("""SELECT vp.canonical_name, vf.category, vf.attribute, vf.value,
                                     vf.confidence, vf.page_start, vf.page_end, vf.scene_id, vf.evidence
                              FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id
                              WHERE vp.document_id=? ORDER BY vf.confidence DESC, vf.id LIMIT ?""", (document_id, sample_size)).fetchall()
        return {"high_confidence_profiles": [dict(r) for r in profiles], "high_confidence_facts": [dict(r) for r in facts]}

    @staticmethod
    def _readiness(report: dict[str, Any]) -> dict[str, Any]:
        coverage = report["coverage"]
        quality = report["fact_quality"]
        context_ok = coverage["scene_context_coverage_pct"] >= 95
        evidence_ok = coverage["fact_evidence_coverage_pct"] >= 95
        confidence_ok = quality["mean_category_confidence"] >= 0.55
        score = sum((context_ok, evidence_ok, confidence_ok)) / 3 * 100
        return {
            "score": round(score, 1),
            "scene_context_ok": context_ok,
            "evidence_coverage_ok": evidence_ok,
            "confidence_baseline_ok": confidence_ok,
            "status": "PASS" if score == 100 else "NEEDS_REVIEW",
            "note": "This is a data-quality gate, not a claim that visual extraction is semantically complete.",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit visual knowledge bible quality")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = VisualBibleAudit(args.database).run(args.document_id, max(1, args.sample_size))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
