from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from .models import PipelineConfig
from .orchestrator import ImageGenerationPipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate source-grounded images through visible Google AI Mode in Chrome."
    )
    parser.add_argument("package")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-order", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--generation-timeout", type=float, default=240)
    parser.add_argument("--vision-model", default=os.getenv("SOCIAL_AUTOMATION_VISION_MODEL", "qwen2.5vl:7b"))
    parser.add_argument("--no-vision", action="store_true")
    parser.add_argument("--no-previous-reference", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--chrome-user-data-dir",
        default=os.getenv("SOCIAL_AUTOMATION_CHROME_USER_DATA_DIR"),
        help="Chrome User Data directory to reuse for the signed-in browser profile.",
    )
    parser.add_argument(
        "--chrome-profile-directory",
        default=os.getenv("SOCIAL_AUTOMATION_CHROME_PROFILE", "Default"),
        help="Chrome profile directory name inside User Data (default: Default).",
    )
    parser.add_argument(
        "--chrome-cdp-url",
        default=os.getenv("SOCIAL_AUTOMATION_CHROME_CDP_URL"),
        help="Connect to an already-running manually signed-in Chrome via CDP.",
    )
    args = parser.parse_args()

    package = Path(args.package)
    output = Path(args.output_dir) if args.output_dir else package.parent / "generated_images"
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config = PipelineConfig(
        package_path=package,
        output_dir=output,
        limit=args.limit,
        start_order=args.start_order,
        max_attempts=max(1, args.max_attempts),
        generation_timeout_s=max(30.0, args.generation_timeout),
        use_previous_reference=not args.no_previous_reference,
        vision_validation=not args.no_vision,
        vision_model=args.vision_model,
        chrome_user_data_dir=Path(args.chrome_user_data_dir) if args.chrome_user_data_dir else None,
        chrome_profile_directory=args.chrome_profile_directory if args.chrome_user_data_dir else None,
        chrome_cdp_url=args.chrome_cdp_url,
    )

    pipeline = ImageGenerationPipeline(config)
    try:
        result = pipeline.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print("Interrupted. SQLite state preserves completed scenes; rerun to resume.")
        return 130
    finally:
        pipeline.close()


if __name__ == "__main__":
    raise SystemExit(main())
