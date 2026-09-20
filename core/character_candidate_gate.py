from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS character_candidate_gate (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    score REAL NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(document_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_character_candidate_gate_doc_decision
    ON character_candidate_gate(document_id, decision);
"""

STOPWORDS = set(
    "a an and are as at be been before but by can could did do does for from had has have he her here him his how i if in is it its just like many more most my never no not now of on one or only or perhaps quite rather said see she so some such than that the their them then there these they this those through to too two under up us very was we were what when where which while why who will with without would you your after above about again almost already also always another any anyone anything around because behind below between both during each either enough every everywhere except few first following further get got great half however indeed instead itself last less little long maybe most much neither next none nothing often once other otherwise over same several since someone something soon still though three together toward towards until upon well whatever whenever whether within yet having ice all besides certainly come doubtless hence".split()
)
NON_PERSON = set(
    "african english englishman european french icelandic icelanders russians danish makololos makololo bochjesmen queen earth orange reykjawik sneffels mother earth".split()
)
TITLE_ONLY = re.compile(
    r"^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame)\.?$",
    re.I,
)
PERSON_TITLE = re.compile(
    r"^(?:mr|mrs|ms|miss|dr|prof|professor|capt|captain|sir|lady|lord|rev|reverend|colonel|major|lieutenant|herr|monsieur|madame|king|emperor|maharaja|maharani|prince|princess|queen)\.?\s+",
    re.I,
)
NAME_WORD = re.compile(r"^[A-Z][A-Za-z'’-]+$")
SPEECH_CUE = re.compile(
    r"\b(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|continued|added|called)\b",
    re.I,
)
ACTION_CUE = re.compile(
    r"\b(?:he|she|his|her)\s+(?:said|replied|asked|cried|shouted|looked|turned|stood|sat|walked|ran|came|went|took|gave|held|put|made)\b",
    re.I,
)
PHYSICAL_SUBJECT_CUE = re.compile(
    r"\b(?:approach\w*|arriv\w*|attack\w*|capture\w*|climb\w*|come|cross\w*|cry\w*|die\w*|enter\w*|fall\w*|flee\w*|follow\w*|fight\w*|fought|grab\w*|hold\w*|kill\w*|look\w*|move\w*|open\w*|reach\w*|return\w*|run\w*|save\w*|sit\w*|stand\w*|take\w*|turn\w*|walk\w*|watch\w*|travel\w*|strike\w*|kneel\w*|rise\w*|speak\w*|stood|sat|lay|remained|waited|rested|entered|arrived|appeared|left|returned|looked|watched|faced|knelt|rose|walked|ran|fled|followed|held|carried|spoke|sang|wept|cried)\b",
    re.I,
)
COPULA_PHYSICAL = re.compile(
    r"\b(?:was|were|is|are)\s+(?:standing|stood|sitting|sat|lying|lay|walking|walked|running|ran|fighting|fought|moving|moved|waiting|waited|resting|rested|kneeling|knelt|looking|looked|watching|watched|facing|carrying|holding|held|entering|entered|leaving|left|returning|returned|speaking|spoke|crying|weeping|wept|falling|fell|captured|killed|wounded|burning|climbing|climbed|approaching|approached|arriving|arrived|riding|rode|seated)\b",
    re.I,
)
DIRECT_PERSON_CUE = re.compile(
    r"(?:\b(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|called)\s+{name}\b|\b{name}\s+(?:said|replied|asked|cried|shouted|exclaimed|answered|whispered|remarked|observed|rejoined|called)\b|\b(?:Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?|Professor|Prof\.?|Captain|Capt\.?|Sir|Colonel|Major|Lieutenant|King|Emperor|Maharaja|Maharani|Prince|Princess|Queen)\s+{name}\b)",
    re.I,
)
ROLE_TOKENS = {
    "river", "rivers", "mount", "mountain", "mountains", "lake", "ocean", "sea", "island", "islands",
    "colony", "republic", "government", "commission", "observatory", "institution", "post", "world",
    "africa", "hope", "zambesi", "cape", "port", "town", "city", "village", "forest", "valley",
    "country", "countrymen", "empire", "kingdom", "company", "society", "school", "university", "museum",
    "academy", "station", "road", "roads", "falls", "fall", "gulfs", "gulf", "desert", "coast", "shore",
    "bay", "peninsula", "expedition", "party", "tribe", "people", "new", "zealand", "atlantic", "balearic",
    "central", "subterranean",
}


IDENTITY_QUALIFIER_WORDS = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "professor", "capt", "captain",
    "sir", "lady", "lord", "rev", "reverend", "colonel", "major", "lieutenant",
    "herr", "monsieur", "madame", "king", "emperor", "maharaja", "maharani",
    "prince", "princess", "queen",
}


def character_name_variants(name: str) -> list[str]:
    """Return only conservative source-name variants implied by an identity title."""
    canonical = norm(name)
    if not canonical:
        return []
    variants = [canonical]
    parts = canonical.split()
    while len(parts) > 1 and parts[0].casefold().rstrip(".") in IDENTITY_QUALIFIER_WORDS:
        parts = parts[1:]
        stripped = " ".join(parts).strip()
        if stripped and stripped.casefold() not in {v.casefold() for v in variants}:
            variants.append(stripped)
    return variants


def norm(name: str) -> str:
    s = re.sub(r"\s+", " ", name.replace("‐", "-").replace("‑", "-").replace("‒", "-").replace("–", "-").replace("—", "-")).strip(" ,.;:\"'")
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    return s[:-1] if s.endswith("-") and len(s) > 3 else s


def physical_presence_count(name: str, contexts: list[str]) -> int:
    """Count contexts where the named candidate or a safe titled form is physically present."""
    name_patterns = [re.escape(value) for value in character_name_variants(name)]
    name_pattern = "(?:" + "|".join(name_patterns) + ")"
    count = 0
    for context in contexts:
        sentences = re.split(r"(?<=[.!?])\s+", context)
        matched = False
        for index, sentence in enumerate(sentences):
            if not re.search(rf"\b{name_pattern}\b", sentence, re.I):
                continue
            # A canonical name can be attached to a place/entity description
            # ("my capital, Trikota", "Trikota was ... city"). Such predicates
            # are not evidence that a person is physically present.
            location_context = re.search(
                rf"(?:\b(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b\s*,\s*\b{name_pattern}\b|"
                rf"\b{name_pattern}\b\s*,\s*(?:the\s+)?(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b|"
                rf"\b{name_pattern}\b\s+(?:was|were|is|are)\s+(?:the\s+)?(?:greatest\s+|finest\s+|largest\s+|smallest\s+)?(?:capital|city|town|village|kingdom|empire|island|river|mountain|temple|palace|fort|country|province|region|world)\b)",
                sentence,
                re.I,
            )
            if location_context:
                continue
            if re.search(rf"\b{name_pattern}\b\s+{PHYSICAL_SUBJECT_CUE.pattern}", sentence, re.I):
                matched = True
                break
            if re.search(rf"\b{name_pattern}\b\s+{COPULA_PHYSICAL.pattern}", sentence, re.I):
                matched = True
                break
            if re.search(rf"\b{name_pattern}\b\s+(?:was|were|is|are)\s+(?:captured|wounded|killed|carried|held|seen|found)\b", sentence, re.I):
                matched = True
                break
            # Explicit narrative identification may introduce the character by
            # name and then describe that identified figure in the next sentence.
            # Keep this narrowly anchored to identity language plus a person
            # descriptor and physical predicate; do not infer presence from
            # arbitrary verbs merely occurring near a name.
            if re.search(rf"\bnone\s+other\s+than\s+{name_pattern}\b", sentence, re.I):
                for following in sentences[index + 1:index + 2]:
                    if re.search(
                        r"\b(?:a|an|the)\b[^.!?]{0,80}\b(?:man|woman|boy|girl|asura|rakshasa|warrior|soldier|king|prince|queen|figure|person)\b[^.!?]{0,80}"
                        + PHYSICAL_SUBJECT_CUE.pattern,
                        following,
                        re.I,
                    ):
                        matched = True
                        break
                if matched:
                    break
        if matched:
            count += 1
    return count


def gate(
    name: str,
    entity_type: str,
    mentions: list[sqlite3.Row],
    *,
    conflicting_entity_types: set[str] | None = None,
) -> tuple[str, float, list[str]]:
    n = norm(name)
    low = n.lower()
    reasons: list[str] = []
    if entity_type != "character":
        return "non_character", 1.0, ["upstream_type_not_character"]
    if TITLE_ONLY.match(n):
        return "non_character", 1.0, ["title_only"]
    if low in STOPWORDS or low in NON_PERSON:
        return "non_character", 1.0, ["common_word_or_demographic_term"]
    raw = name.strip()
    if raw.endswith(("-", "‐", "‑", "‒", "–", "—")):
        return "review", 0.4, ["line_break_fragment"]
    if len(n) < 3 or len(n) > 45:
        return "review", 0.9, ["name_length_anomaly"]
    words = n.replace("-", " ").split()
    title = bool(PERSON_TITLE.match(n))
    bare = [
        w.strip(".")
        for w in words
        if w.lower() not in {"mr", "mrs", "ms", "miss", "dr", "prof", "professor", "capt", "captain", "sir", "lady", "lord", "rev", "reverend", "colonel", "major", "lieutenant", "herr", "monsieur", "madame", "king", "emperor", "maharaja", "maharani", "prince", "princess", "queen"}
    ]
    if not all(NAME_WORD.match(w) for w in bare if w):
        return "review", 0.65, ["non_name_token"]
    roles = {w.lower().rstrip(".") for w in bare}
    if not title and roles & ROLE_TOKENS:
        return "non_character", 0.95, ["generic_non_person_name_pattern"]
    contexts = [str(m["context"] or "") for m in mentions]
    observed_names = []
    safe_variant_keys = {value.casefold() for value in character_name_variants(n)}
    for mention in mentions:
        try:
            mention_text = str(mention["mention_text"] or "").strip()
        except (KeyError, IndexError):
            mention_text = ""
        if mention_text and mention_text.casefold() in safe_variant_keys:
            observed_names.append(mention_text)
    evidence_names = list(dict.fromkeys(character_name_variants(n) + observed_names))
    evidence_pattern = "(?:" + "|".join(re.escape(value) for value in evidence_names) + ")"
    exact = sum(1 for x in contexts if re.search(rf"\b{evidence_pattern}\b", x, re.I))
    scenes = len({m["scene_id"] for m in mentions if m["scene_id"] is not None})
    speech = sum(1 for x in contexts if SPEECH_CUE.search(x))
    action = sum(1 for x in contexts if ACTION_CUE.search(x))
    direct = sum(1 for x in contexts if re.search(DIRECT_PERSON_CUE.pattern.format(name=evidence_pattern), x, re.I))
    physical = max((physical_presence_count(value, contexts) for value in evidence_names), default=0)

    if conflicting_entity_types and conflicting_entity_types & {"location", "environment"}:
        if direct == 0 and physical == 0:
            return "non_character", 1.0, ["ambiguous_name_without_person_evidence"]
        reasons.append("name_also_classified_as_location_or_environment")

    if title and len(bare) == 1 and bare[0].lower() in STOPWORDS and direct == 0 and physical == 0:
        return "review", 0.35, ["title_with_stopword_name_without_direct_person_reference"]
    score = 0.25
    if title:
        score += 0.25; reasons.append("personal_title")
    if len(bare) >= 2:
        score += 0.15; reasons.append("multiword_person_name")
    if exact >= 2:
        score += 0.15; reasons.append("name_patternpeated_in_context")
    if len(mentions) >= 3:
        score += 0.10; reasons.append("recurring_mentions")
    if scenes >= 2:
        score += 0.10; reasons.append("multi_scene_presence")
    if direct:
        score += 0.25; reasons.append("direct_person_reference")
    if physical:
        score += min(0.30, physical * 0.30); reasons.append("source_physical_presence")
    if speech:
        score += 0.05; reasons.append("speech_context")
    if action:
        score += 0.05; reasons.append("character_action_context")
    if any(w.lower() in STOPWORDS for w in bare):
        score -= 0.45; reasons.append("stopword_name_component")
    if len(bare) == 1 and not title and direct == 0 and physical == 0:
        score = min(score, 0.44); reasons.append("single_word_without_direct_person_reference")
    if len(bare) >= 2 and not title and direct == 0 and physical == 0 and exact < 3:
        score = min(score, 0.47); reasons.append("untitled_name_without_repeated_direct_evidence")
    score = max(0, min(1, score))
    decision = "validated" if score >= 0.75 else "probable" if score >= 0.48 else "review"
    return decision, score, reasons


def build(db: str | Path, document_id: int) -> dict[str, int]:
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)
        con.execute("DELETE FROM character_candidate_gate WHERE document_id=?", (document_id,))
        entities = con.execute(
            "SELECT id,entity_type,canonical_name FROM entities WHERE document_id=? ORDER BY id",
            (document_id,),
        ).fetchall()
        names_by_entity_type: dict[str, set[str]] = {}
        for entity in entities:
            names_by_entity_type.setdefault(norm(entity["canonical_name"]).lower(), set()).add(str(entity["entity_type"]))
        for e in entities:
            mentions = con.execute(
                "SELECT scene_id,context,mention_text FROM entity_mentions WHERE document_id=? AND entity_id=? ORDER BY page_start,id",
                (document_id, e["id"]),
            ).fetchall()
            conflicting = names_by_entity_type.get(norm(e["canonical_name"]).lower(), set()) - {str(e["entity_type"])}
            decision, score, reasons = gate(
                e["canonical_name"],
                e["entity_type"],
                mentions,
                conflicting_entity_types=conflicting,
            )
            con.execute(
                "INSERT INTO character_candidate_gate(document_id,entity_id,decision,normalized_name,score,reasons_json) VALUES(?,?,?,?,?,?)",
                (document_id, e["id"], decision, norm(e["canonical_name"]), score, json.dumps(reasons)),
            )
        con.commit()
        return {r["decision"]: int(r["n"]) for r in con.execute("SELECT decision,COUNT(*) n FROM character_candidate_gate WHERE document_id=? GROUP BY decision", (document_id,)).fetchall()}


def main() -> None:
    p = argparse.ArgumentParser(description="Conservative character candidate gate")
    p.add_argument("db", type=str)
    p.add_argument("document_id", type=int)
    a = p.parse_args()
    r = build(a.db, a.document_id)
    print("=== CHARACTER CANDIDATE GATE ===")
    for k in ("validated", "probable", "review", "non_character"):
        print(f"{k}: {r.get(k, 0)}")


if __name__ == "__main__":
    main()


# Backward-compatible alias for internal callers/tests that used the former private helper.
_physical_presence = physical_presence_count
