from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

from .pipeline import run as run_document_pipeline
from .prompt_export import build_all_prompts


def run(
    pdf_path: str | Path,
    *,
    max_pages: int | None = None,
    llm_mode: str | None = None,
    llm_model: str | None = None,
    llm_timeout: float | None = None,
) -> dict:
    """Process a PDF through the architecture and export all prompts."""
    if llm_mode is not None:
        normalized_mode = llm_mode.strip().lower()
        if normalized_mode not in {"off", "shadow", "enhance"}:
            raise ValueError("llm_mode must be one of: off, shadow, enhance")
        os.environ["SOCIAL_AUTOMATION_LLM_MODE"] = normalized_mode
    if llm_model:
        os.environ["SOCIAL_AUTOMATION_LLM_MODEL"] = llm_model.strip()
    if llm_timeout is not None:
        if llm_timeout <= 0:
            raise ValueError("llm_timeout must be greater than zero")
        os.environ["SOCIAL_AUTOMATION_LLM_TIMEOUT"] = str(llm_timeout)

    pdf_path = Path(pdf_path)
    structure, document_id = run_document_pipeline(pdf_path, max_pages=max_pages)
    database_path = pdf_path.parent / f"{pdf_path.stem}_structure.db"

    with sqlite3.connect(database_path) as con:
        scene_total = int(con.execute("SELECT COUNT(*) FROM scenes WHERE document_id=?", (document_id,)).fetchone()[0])
    os.environ["SOCIAL_AUTOMATION_PROGRESS_TOTAL"] = str(scene_total)

    prompt_result = build_all_prompts(database_path, document_id)
    return {
        "pdf": str(pdf_path),
        "document_id": document_id,
        "pages": len(structure.pages),
        "sections": len(structure.sections),
        "database": str(database_path),
        "llm_mode": os.getenv("SOCIAL_AUTOMATION_LLM_MODE", "off"),
        "llm_model": os.getenv("SOCIAL_AUTOMATION_LLM_MODEL", "qwen3:30b"),
        "llm_timeout": float(os.getenv("SOCIAL_AUTOMATION_LLM_TIMEOUT", "900")),
        "scene_total": scene_total,
        "prompt_export": prompt_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Definition-of-done pipeline: PDF -> source structure -> identity/visual/continuity -> all prompts")
    parser.add_argument("pdf")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--llm-mode", choices=["off", "shadow", "enhance"], default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-timeout", type=float, default=None, help="Per-scene Ollama timeout in seconds; default 900")
    args = parser.parse_args()
    result = run(args.pdf, max_pages=args.max_pages, llm_mode=args.llm_mode, llm_model=args.llm_model, llm_timeout=args.llm_timeout)
    print("\n" + "=" * 60)
    print("DOD COMPLETE")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["prompt_export"]["qa_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
