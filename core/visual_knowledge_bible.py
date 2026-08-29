from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_profiles (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL,
    profile_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0,
    UNIQUE(document_id, profile_type, canonical_name)
);

CREATE TABLE IF NOT EXISTS visual_facts (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES visual_profiles(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'supported',
    source_type TEXT NOT NULL,
    source_id INTEGER,
    scene_id INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    evidence TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    extraction_method TEXT NOT NULL,
    UNIQUE(profile_id, category, attribute, value, source_type, source_id, scene_id)
);

CREATE INDEX IF NOT EXISTS idx_visual_profiles_document
    ON visual_profiles(document_id, profile_type);
CREATE INDEX IF NOT EXISTS idx_visual_facts_profile
    ON visual_facts(profile_id, category, attribute);
CREATE INDEX IF NOT EXISTS idx_visual_facts_scene
    ON visual_facts(scene_id);

CREATE TABLE IF NOT EXISTS scene_visual_context (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    character_profile_ids TEXT NOT NULL DEFAULT '[]',
    environment_profile_ids TEXT NOT NULL DEFAULT '[]',
    object_mentions TEXT NOT NULL DEFAULT '[]',
    continuity_json TEXT NOT NULL DEFAULT '{}',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, scene_id)
);

CREATE TABLE IF NOT EXISTS visual_objects (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    canonical_name TEXT NOT NULL,
    profile_text TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    discovery_method TEXT NOT NULL,
    UNIQUE(document_id, canonical_name)
);

CREATE TABLE IF NOT EXISTS visual_object_mentions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    object_id INTEGER NOT NULL REFERENCES visual_objects(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    page_start INTEGER,
    page_end INTEGER,
    evidence TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    UNIQUE(object_id, scene_id)
);
"""


class VisualKnowledgeBible:
    """Build an evidence-first visual continuity layer from the existing store.

    No generative facts are created. Every fact is tied to source text and a
    page/scene where available. Missing attributes remain absent rather than
    being guessed. The layer is deliberately independent of any LLM so it can
    be audited before generation.
    """

    CHARACTER_PATTERNS = {
        "age": [
            re.compile(r"\b(?:aged|age[d]?|about|nearly|approximately)\s+(\d{1,3})\s*(?:years?|yrs?)\b", re.I),
            re.compile(r"\b(\d{1,3})[- ]year[- ]old\b", re.I),
        ],
        "height": [
            re.compile(r"\b(?:about|nearly|approximately|some)\s+([\d'\".,]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\b", re.I),
            re.compile(r"\b([\d]+\s*(?:feet|foot|ft|inches|inch|in|metres|meters|m|cm))\s+(?:high|tall)\b", re.I),
        ],
        "build": [
            re.compile(r"\b((?:very|quite|rather|extremely|remarkably|slightly)?\s*(?:tall|short|large|small|slender|thin|lean|slight|stout|stocky|broad|muscular|powerful|robust|strong|weak|lanky|massive|heavy|delicate))\b", re.I),
        ],
        "hair": [
            re.compile(r"\b((?:long|short|thick|thin|curly|straight|wavy|dark|black|brown|fair|blond|blonde|grey|gray|white|red|auburn)\s+(?:hair|locks|tresses))\b", re.I),
            re.compile(r"\b(?:hair|beard|moustache|mustache)\s+(?:was|were|is|of)\s+([^.;,]{2,50})", re.I),
        ],
        "facial_hair": [
            re.compile(r"\b((?:long|short|full|thick|heavy|bushy|black|brown|grey|gray|white|red)?\s*(?:beard|moustache|mustache|whiskers))\b", re.I),
        ],
        "eyes": [
            re.compile(r"\b((?:blue|green|grey|gray|brown|black|hazel|dark|bright|deep|large|small|piercing|keen|sharp)\s+eyes?)\b", re.I),
        ],
        "complexion": [
            re.compile(r"\b((?:pale|fair|dark|ruddy|florid|sallow|swarthy|tanned|sunburnt|sunburned|weathered|fresh|healthy|worn|haggard)\s+(?:face|complexion|skin))\b", re.I),
        ],
        "face": [
            re.compile(r"\b((?:round|oval|long|broad|thin|narrow|square|angular|handsome|ugly|rugged|stern|kind|intelligent|expressive)\s+(?:face|features|countenance))\b", re.I),
        ],
        "distinctive_mark": [
            re.compile(r"\b(?:scar|scars|mark|marks|birthmark|tattoo|wound|injury)\b[^.;]{0,100}", re.I),
        ],
        "clothing": [
            re.compile(r"\b(?:wearing|wore|dressed in|clad in|attired in)\s+([^.;]{3,140})", re.I),
            re.compile(r"\b((?:coat|cloak|jacket|shirt|trousers|pants|dress|skirt|boots|shoes|hat|cap|helmet|gloves|scarf|belt|uniform|suit|vest|waistcoat|tunic|gown|sleeves?))\b", re.I),
        ],
        "expression": [
            re.compile(r"\b((?:smiling|smiled|laughing|laughed|angry|furious|frightened|afraid|terrified|calm|anxious|worried|sad|joyful|cheerful|stern|serious|grave|excited|astonished|surprised|pale with fear))\b", re.I),
        ],
        "mannerism": [
            re.compile(r"\b((?:habitually|always|often|usually|constantly)\s+[^.;]{3,120})", re.I),
        ],
    }

    ENV_PATTERNS = {
        "weather": re.compile(r"\b((?:cold|hot|warm|freezing|icy|snowy|stormy|windy|foggy|misty|rainy|raining|sunny|dark|cloudy|clear|humid|dry)\s+(?:weather|air|wind|sky|day|night))\b", re.I),
        "terrain": re.compile(r"\b((?:steep|rocky|rugged|rough|smooth|flat|narrow|wide|deep|vast|dark|icy|snow-covered|snowy|volcanic|sandy|muddy|forested|barren)\s+(?:mountain|mountains|valley|plain|plains|road|shore|bank|banks|cave|cavern|tunnel|gallery|shaft|coast|island|islands|ground|terrain))\b", re.I),
        "light": re.compile(r"\b((?:bright|dim|dark|faint|brilliant|dazzling|sunlit|moonlit|shadowy|gloomy|red|blue|golden)\s+(?:light|glow|illumination|daylight|sunlight|moonlight))\b", re.I),
        "atmosphere": re.compile(r"\b((?:silent|quiet|noisy|oppressive|eerie|mysterious|terrible|terrific|beautiful|magnificent|desolate|lonely|cheerful|pleasant|stifling|suffocating|humid|damp|dry)\s+(?:atmosphere|air|place|scene|silence|stillness))\b", re.I),
        "material": re.compile(r"\b((?:rock|stone|ice|snow|sand|water|lava|basalt|granite|clay|wooden|wood|metal|iron|steel|glass|leather|brick|marble)\s+(?:wall|walls|floor|floors|ceiling|rock|rocks|ground|surface|door|doors|bridge|structure|material))\b", re.I),
    }

    OBJECT_TERMS = {
        "map", "compass", "lantern", "lamp", "rope", "pickaxe", "axe", "hammer",
        "rifle", "gun", "pistol", "knife", "dagger", "sword", "bag", "backpack",
        "satchel", "bottle", "flask", "book", "journal", "diary", "letter", "parchment",
        "instrument", "thermometer", "barometer", "telescope", "microscope", "boat",
        "raft", "carriage", "wagon", "vehicle", "machine", "key", "door", "bridge",
    }

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def build(self, document_id: int) -> dict[str, int]:
        with sqlite3.connect(self.database_path) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            con.executescript(SCHEMA)
            self._clear_document(con, document_id)
            entities = con.execute(
                "SELECT id, entity_type, canonical_name, profile_text, confidence FROM entities WHERE document_id=? ORDER BY id",
                (document_id,),
            ).fetchall()
            scenes = con.execute(
                "SELECT id, story_id, title, page_start, page_end, text FROM scenes WHERE document_id=? ORDER BY story_id, scene_order",
                (document_id,),
            ).fetchall()

            entity_profiles: dict[int, int] = {}
            for entity in entities:
                ptype = self._profile_type(entity["entity_type"])
                if ptype is None:
                    continue
                profile_id = self._profile(con, document_id, int(entity["id"]), ptype, entity["canonical_name"], float(entity["confidence"] or 0))
                entity_profiles[int(entity["id"])] = profile_id

                mentions = con.execute(
                    """SELECT em.scene_id, em.page_start, em.page_end, em.context, em.confidence,
                              s.text AS scene_text
                       FROM entity_mentions em JOIN scenes s ON s.id=em.scene_id
                       WHERE em.document_id=? AND em.entity_id=? ORDER BY em.page_start, em.id""",
                    (document_id, int(entity["id"])),
                ).fetchall()
                for mention in mentions:
                    text = str(mention["context"] or "")
                    self._extract_character_facts(con, profile_id, int(mention["scene_id"]), int(mention["page_start"]), int(mention["page_end"]), text, float(mention["confidence"] or 0.5))

                if entity["profile_text"]:
                    self._add_fact(con, profile_id, "source_profile", "profile_evidence", str(entity["profile_text"]), "entity", int(entity["id"]), None, None, None, str(entity["profile_text"]), float(entity["confidence"] or 0.5), "existing_entity_evidence")

            object_ids = self._build_objects(con, document_id, scenes)
            self._build_scene_context(con, document_id, scenes, entity_profiles, object_ids)
            self._build_environment_facts(con, document_id, scenes, entity_profiles)
            con.commit()

            counts = {
                "profiles": con.execute("SELECT COUNT(*) FROM visual_profiles WHERE document_id=?", (document_id,)).fetchone()[0],
                "facts": con.execute("SELECT COUNT(*) FROM visual_facts vf JOIN visual_profiles vp ON vp.id=vf.profile_id WHERE vp.document_id=?", (document_id,)).fetchone()[0],
                "objects": con.execute("SELECT COUNT(*) FROM visual_objects WHERE document_id=?", (document_id,)).fetchone()[0],
                "object_mentions": con.execute("SELECT COUNT(*) FROM visual_object_mentions WHERE document_id=?", (document_id,)).fetchone()[0],
                "scene_context": con.execute("SELECT COUNT(*) FROM scene_visual_context WHERE document_id=?", (document_id,)).fetchone()[0],
            }
            return {k: int(v) for k, v in counts.items()}

    @staticmethod
    def _clear_document(con: sqlite3.Connection, document_id: int) -> None:
        con.execute("DELETE FROM scene_visual_context WHERE document_id=?", (document_id,))
        con.execute("DELETE FROM visual_object_mentions WHERE document_id=?", (document_id,))
        con.execute("DELETE FROM visual_objects WHERE document_id=?", (document_id,))
        con.execute("DELETE FROM visual_facts WHERE profile_id IN (SELECT id FROM visual_profiles WHERE document_id=?)", (document_id,))
        con.execute("DELETE FROM visual_profiles WHERE document_id=?", (document_id,))

    @staticmethod
    def _profile_type(entity_type: str) -> str | None:
        if entity_type == "character":
            return "character"
        if entity_type in {"location", "environment"}:
            return "environment"
        return None

    @staticmethod
    def _profile(con, document_id: int, entity_id: int, profile_type: str, name: str, confidence: float) -> int:
        con.execute(
            "INSERT INTO visual_profiles(document_id,entity_id,profile_type,canonical_name,confidence) VALUES(?,?,?,?,?)",
            (document_id, entity_id, profile_type, name, confidence),
        )
        return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])

    def _extract_character_facts(self, con, profile_id: int, scene_id: int, page_start: int, page_end: int, text: str, base_confidence: float) -> None:
        for attribute, patterns in self.CHARACTER_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    value = self._clean_value(match.group(1) if match.lastindex else match.group(0))
                    if not value:
                        continue
                    evidence = self._evidence(text, match.start(), match.end())
                    self._add_fact(con, profile_id, "appearance" if attribute not in {"clothing", "expression", "mannerism"} else attribute, attribute, value, "scene", None, scene_id, page_start, page_end, evidence, min(0.98, max(0.35, base_confidence)), "source_pattern")

    def _build_environment_facts(self, con, document_id: int, scenes: list[sqlite3.Row], entity_profiles: dict[int, int]) -> None:
        env_ids = con.execute("SELECT id FROM entities WHERE document_id=? AND entity_type IN ('environment','location')", (document_id,)).fetchall()
        env_set = {int(r[0]) for r in env_ids}
        for scene in scenes:
            text = str(scene["text"] or "")
            mentioned = con.execute("SELECT entity_id FROM entity_mentions WHERE document_id=? AND scene_id=?", (document_id, int(scene["id"]))).fetchall()
            for row in mentioned:
                eid = int(row[0])
                if eid not in env_set or eid not in entity_profiles:
                    continue
                profile_id = entity_profiles[eid]
                for category, pattern in self.ENV_PATTERNS.items():
                    for match in pattern.finditer(text):
                        value = self._clean_value(match.group(1))
                        evidence = self._evidence(text, match.start(), match.end())
                        self._add_fact(con, profile_id, category, category, value, "scene", None, int(scene["id"]), int(scene["page_start"]), int(scene["page_end"]), evidence, 0.65, "source_pattern")

    def _build_objects(self, con, document_id: int, scenes: list[sqlite3.Row]) -> dict[str, int]:
        object_ids: dict[str, int] = {}
        for scene in scenes:
            text = str(scene["text"] or "")
            words = set(re.findall(r"\b[A-Za-z][A-Za-z'-]+\b", text.lower()))
            for term in sorted(words & self.OBJECT_TERMS):
                name = term.title()
                row = con.execute("SELECT id FROM visual_objects WHERE document_id=? AND canonical_name=?", (document_id, name)).fetchone()
                if row:
                    oid = int(row[0])
                else:
                    con.execute("INSERT INTO visual_objects(document_id,canonical_name,confidence,discovery_method) VALUES(?,?,?,?)", (document_id, name, 0.55, "visual_prop_lexicon"))
                    oid = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
                object_ids[name] = oid
                evidence = self._term_evidence(text, term)
                con.execute(
                    "INSERT OR IGNORE INTO visual_object_mentions(document_id,object_id,scene_id,page_start,page_end,evidence,confidence) VALUES(?,?,?,?,?,?,?)",
                    (document_id, oid, int(scene["id"]), int(scene["page_start"]), int(scene["page_end"]), evidence, 0.55),
                )
                current = con.execute("SELECT profile_text FROM visual_objects WHERE id=?", (oid,)).fetchone()[0] or ""
                if evidence and evidence not in current:
                    merged = (current + "\n\n" + evidence).strip()[:6000]
                    con.execute("UPDATE visual_objects SET profile_text=? WHERE id=?", (merged, oid))
        return object_ids

    def _build_scene_context(self, con, document_id: int, scenes: list[sqlite3.Row], entity_profiles: dict[int, int], object_ids: dict[str, int]) -> None:
        for scene in scenes:
            sid = int(scene["id"])
            mentions = con.execute(
                "SELECT DISTINCT entity_id FROM entity_mentions WHERE document_id=? AND scene_id=? ORDER BY entity_id",
                (document_id, sid),
            ).fetchall()
            char_profiles = []
            env_profiles = []
            for row in mentions:
                eid = int(row[0])
                pid = entity_profiles.get(eid)
                if pid is None:
                    continue
                etype = con.execute("SELECT profile_type FROM visual_profiles WHERE id=?", (pid,)).fetchone()[0]
                (char_profiles if etype == "character" else env_profiles).append(pid)
            text = str(scene["text"] or "")
            words = set(re.findall(r"\b[A-Za-z][A-Za-z'-]+\b", text.lower()))
            object_mentions = [object_ids[w.title()] for w in sorted(words & self.OBJECT_TERMS) if w.title() in object_ids]
            evidence = []
            for term in sorted(words & self.OBJECT_TERMS):
                ev = self._term_evidence(text, term)
                if ev:
                    evidence.append({"object": term, "evidence": ev})
            continuity = {
                "persistent_character_profiles": char_profiles,
                "environment_profiles": env_profiles,
                "object_profile_ids": object_mentions,
                "source_grounded": True,
                "unknowns_must_remain_unknown": True,
            }
            con.execute(
                "INSERT INTO scene_visual_context(document_id,scene_id,character_profile_ids,environment_profile_ids,object_mentions,continuity_json,evidence_json) VALUES(?,?,?,?,?,?,?)",
                (document_id, sid, json.dumps(char_profiles), json.dumps(env_profiles), json.dumps(object_mentions), json.dumps(continuity, sort_keys=True), json.dumps(evidence, ensure_ascii=False)),
            )

    @staticmethod
    def _add_fact(con, profile_id: int, category: str, attribute: str, value: str, source_type: str, source_id: int | None, scene_id: int | None, page_start: int | None, page_end: int | None, evidence: str, confidence: float, method: str) -> None:
        con.execute(
            """INSERT OR IGNORE INTO visual_facts
               (profile_id,category,attribute,value,status,source_type,source_id,scene_id,page_start,page_end,evidence,confidence,extraction_method)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (profile_id, category, attribute, value, "supported", source_type, source_id, scene_id, page_start, page_end, evidence, confidence, method),
        )

    @staticmethod
    def _clean_value(value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip(" \t\r\n,.;:!?\"'()[]"))
        return value[:300]

    @staticmethod
    def _evidence(text: str, start: int, end: int, radius: int = 180) -> str:
        return text[max(0, start-radius):min(len(text), end+radius)].strip()

    @staticmethod
    def _term_evidence(text: str, term: str, radius: int = 180) -> str:
        match = re.search(r"\b" + re.escape(term) + r"\b", text, re.I)
        if not match:
            return ""
        return VisualKnowledgeBible._evidence(text, match.start(), match.end(), radius)


def build_visual_knowledge_bible(database_path: str | Path, document_id: int) -> dict[str, int]:
    return VisualKnowledgeBible(database_path).build(document_id)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build the source-grounded visual knowledge bible")
    parser.add_argument("database")
    parser.add_argument("document_id", type=int)
    args = parser.parse_args()
    counts = build_visual_knowledge_bible(args.database, args.document_id)
    print("=== VISUAL KNOWLEDGE BIBLE ===")
    for key, value in counts.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
