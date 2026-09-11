from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run as run_document_pipeline
from .prompt_export import build_all_prompts


def run(
    pdf_path: str | Path,
    *,
    max_pages: int | None = None,
    llm_mode: str | None = None,
    llm_model: str | None = None,
) -> dict:
    """Process a PDF through the architecture and export all prompts."""
    if llm_mode is not None:
        normalized_mode = llm_mode.strip().lower()
        if normalized_mode not in {"off", "shadow", "enhance"}:
            raise ValueError("llm_mode must be one of: off, shadow, enhance")
        os.environ["SOCIAL_AUTOMATION_LLM_MODE"] = normalized_mode
    if llm_model:
        os.environ["SOCIAL_AUTOMATION_LLM_MODEL"] = llm_model.strip()

    pdf_path = Path(pdf_path)
    structure, document_id = run_document_pipeline(pdf_path, max_pages=max_pages)
    database_path = pdf_path.parent / f"{pdf_path.stem}_structure.db"
    prompt_result = build_all_prompts(database_path, document_id)
    return {
        "pdf": str(pdf_path),
        "document_id": document_id,
        "pages": len(structure.pages),
        "sections": len(structure.sections),
        "database": str(database_path),
        "llm_mode": os.getenv("SOCIAL_AUTOMATION_LLM_MODE", "off"),
        "llm_model": os.getenv("SOCIAL_AUTOMATION_LLM_MODEL", "qwen3:30b"),
        "prompt_export": prompt_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Definition-of-done pipeline: PDF -> source structure -> identity/visual/continuity -> all prompts"
    )
    parser.add_argument("pdf")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--llm-mode", choices=["off", "shadow", "enhance"], default=None)
    parser.add_argument("--llm-model", default=None)
    args = parser.parse_args()
    result = run(
        args.pdf,
        max_pages=args.max_pages,
        llm_mode=args.llm_mode,
        llm_model=args.llm_model,
    )
    print("\n" + "=" * 60)
    print("DOD COMPLETE")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["prompt_export"]["qa_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
