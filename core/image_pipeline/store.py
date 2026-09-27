from __future__ import annotations
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from .models import JobStatus,SceneJob
def _now(): return datetime.now(timezone.utc).isoformat()
class GenerationStore:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.con=sqlite3.connect(self.path,timeout=30); self.con.row_factory=sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL"); self.con.executescript("""CREATE TABLE IF NOT EXISTS jobs(scene_id INTEGER PRIMARY KEY,scene_order INTEGER NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,prompt_hash TEXT NOT NULL,prompt_path TEXT,final_path TEXT,validation_path TEXT,last_error TEXT,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,scene_id INTEGER,attempt_number INTEGER,prompt_path TEXT,image_path TEXT,validation_path TEXT,status TEXT,failure_reason TEXT,created_at TEXT);CREATE INDEX IF NOT EXISTS idx_jobs_order ON jobs(scene_order);"""); self.con.commit()
    def close(self): self.con.close()
    def ensure_jobs(self,jobs,hashes):
        for j in jobs:
            row=self.con.execute("SELECT prompt_hash FROM jobs WHERE scene_id=?",(j.scene_id,)).fetchone()
            if row is None:self.con.execute("INSERT INTO jobs(scene_id,scene_order,title,status,prompt_hash,updated_at) VALUES(?,?,?,?,?,?)",(j.scene_id,j.scene_order,j.title,JobStatus.PENDING,hashes[j.scene_id],_now()))
            elif row["prompt_hash"]!=hashes[j.scene_id]: self.con.execute("UPDATE jobs SET scene_order=?,title=?,status=?,attempt=0,prompt_hash=?,prompt_path=NULL,final_path=NULL,validation_path=NULL,last_error='prompt changed',updated_at=? WHERE scene_id=?",(j.scene_order,j.title,JobStatus.PENDING,hashes[j.scene_id],_now(),j.scene_id))
        self.con.execute("UPDATE jobs SET status=?,last_error='recovered stale running job',updated_at=? WHERE status=?",(JobStatus.RETRY,_now(),JobStatus.RUNNING)); self.con.commit()
    def get(self,sid): return self.con.execute("SELECT * FROM jobs WHERE scene_id=?",(sid,)).fetchone()
    def set_status(self,sid,status,**fields):
        allowed={"attempt","prompt_path","final_path","validation_path","last_error"}; f={k:(str(v) if isinstance(v,Path) else v) for k,v in fields.items() if k in allowed}; f["status"]=str(status); f["updated_at"]=_now(); self.con.execute("UPDATE jobs SET "+",".join(k+"=?" for k in f)+" WHERE scene_id=?",[*f.values(),sid]); self.con.commit()
    def begin_attempt(self,sid,n,prompt): self.con.execute("INSERT INTO attempts(scene_id,attempt_number,prompt_path,status,created_at) VALUES(?,?,?,?,?)",(sid,n,str(prompt),"started",_now())); self.con.commit()
    def finish_attempt(self,sid,n,**kw): self.con.execute("UPDATE attempts SET status=?,image_path=?,validation_path=?,failure_reason=? WHERE scene_id=? AND attempt_number=?",(kw.get("status"),str(kw["image_path"]) if kw.get("image_path") else None,str(kw["validation_path"]) if kw.get("validation_path") else None,kw.get("failure_reason"),sid,n)); self.con.commit()
    def pending_or_retry(self,limit=None,start_order=None):
        q="SELECT scene_id FROM jobs WHERE status IN (?,?)"; a=[JobStatus.PENDING,JobStatus.RETRY]
        if start_order is not None:q+=" AND scene_order>=?"; a.append(start_order)
        q+=" ORDER BY scene_order,scene_id";
        if limit:q+=" LIMIT ?"; a.append(limit)
        return [int(r["scene_id"]) for r in self.con.execute(q,a)]
    def summary(self): return {str(r["status"]):int(r["n"]) for r in self.con.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")}
