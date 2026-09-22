from __future__ import annotations

import argparse
import os
import sys

from core.ollama_client import OllamaClient, OllamaSettings, OllamaUnavailable


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local Ollama connectivity and model availability")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    if args.model:
        os.environ["SOCIAL_AUTOMATION_LLM_MODEL"] = args.model
    settings = OllamaSettings.from_env()
    print(f"Ollama host: {settings.host}")
    print(f"Requested model: {settings.model}")
    try:
        client = OllamaClient(settings)
        names = client.models()
        print(f"Installed models: {', '.join(names) or '(none)'}")
        client.assert_model_available()
        print("OLLAMA CHECK: PASS")
        return 0
    except OllamaUnavailable as exc:
        print(f"OLLAMA CHECK: FAIL - {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
