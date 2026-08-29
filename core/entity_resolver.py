from __future__ import annotations
import re
import sqlite3
from collections import defaultdict

class EntityResolver:
    """Conservative, deterministic resolution of reusable entity identities."""

    _HONORIFICS = {
        "mr", "mrs", "miss", "ms", "dr", "sir", "captain", "professor",
        "lord", "lady", "king", "queen", "prince", "princess",
    }

    def resolve_connection(self, connection: sqlite3.Connection, document_id: int) -> None:
        connection.execute("DELETE FROM entity_aliases WHERE document_id = ?", (document_id,))
        rows = connection.execute(
            """SELECT id, entity_type, canonical_name, profile_text, confidence, discovery_method
               FROM entities WHERE document_id=? ORDER BY entity_type,id""",
            (document_id,),
        ).fetchall()
        canonical = {int(r["id"]): int(r["id"]) for r in rows}
        aliases = []
        groups = defaultdict(list)
        for r in rows:
            groups[(r["entity_type"], self.normalize(r["canonical_name"]))].append(r)
        for candidates in groups.values():
            winner = sorted(candidates, key=lambda r: (-float(r["confidence"]), int(r["id"])))[0]
            wid = int(winner["id"])
            for r in candidates:
                rid=int(r["id"]); canonical[rid]=wid
                if rid != wid:
                    aliases.append((wid, r["canonical_name"], "normalized_exact", min(float(r["confidence"]), .95)))

        chars=[r for r in rows if r["entity_type"]=="character"]
        for full in chars:
            parts=self.name_parts(full["canonical_name"])
            if len(parts)<2 or parts[0].lower().rstrip(".") not in self._HONORIFICS:
                continue
            short=parts[-1]
            if len(short)<4: continue
            matches=[r for r in chars if self.normalize(r["canonical_name"])==self.normalize(short)]
            if len(matches)!=1: continue
            target=matches[0]
            # Merge only if the titled name is at least as reliable as the short form.
            if float(full["confidence"]) >= float(target["confidence"]):
                cid=int(full["id"])
                old=int(target["id"])
                for k,v in list(canonical.items()):
                    if v==old: canonical[k]=cid
                canonical[old]=cid
                aliases.append((cid, target["canonical_name"], "titled_name_variant", .82))

        for old,new in canonical.items():
            if old!=new:
                connection.execute(
                    "UPDATE entity_mentions SET entity_id=? WHERE document_id=? AND entity_id=?",
                    (new,document_id,old))

        # Aggregate evidence into the canonical profile without inventing attributes.
        for eid in sorted(set(canonical.values())):
            contexts=connection.execute(
                """SELECT context FROM entity_mentions
                   WHERE document_id=? AND entity_id=? ORDER BY page_start,id LIMIT 12""",
                (document_id,eid)).fetchall()
            profile="\n\n".join(str(r["context"]).strip() for r in contexts if str(r["context"]).strip())
            maxconf=connection.execute(
                "SELECT MAX(confidence) FROM entity_mentions WHERE document_id=? AND entity_id=?",
                (document_id,eid)).fetchone()[0]
            if maxconf is not None:
                connection.execute(
                    "UPDATE entities SET profile_text=?, confidence=? WHERE id=? AND document_id=?",
                    (profile[:6000],float(maxconf),eid,document_id))
        for old,new in canonical.items():
            if old!=new:
                connection.execute("DELETE FROM entities WHERE id=?", (old,))

        # Record every surviving canonical spelling plus explicitly resolved aliases.
        seen=set()
        for r in rows:
            cid=canonical.get(int(r["id"]),int(r["id"]))
            key=(cid,r["canonical_name"].lower())
            if key not in seen:
                seen.add(key); aliases.append((cid,r["canonical_name"],"canonical_spelling",1.0))
        for eid,alias,method,conf in aliases:
            connection.execute(
                """INSERT OR IGNORE INTO entity_aliases
                   (document_id,entity_id,alias,resolution_method,confidence)
                   VALUES (?,?,?,?,?)""",
                (document_id,eid,alias,method,conf))
        connection.commit()

    @staticmethod
    def normalize(value:str)->str:
        value=value.lower().strip()
        value=re.sub(r"[’'`]","",value)
        value=re.sub(r"[^a-z0-9\s-]"," ",value)
        return re.sub(r"\s+"," ",value).strip()

    @staticmethod
    def name_parts(value:str)->list[str]:
        return [p for p in re.split(r"\s+",value.strip()) if p]
