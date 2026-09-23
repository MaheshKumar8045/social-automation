from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from .models import PipelineConfig
from .browser import GoogleAIModeDailyLimitError
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
        default=os.getenv("SOCIAL_AUTOMATION_CHROME_CDP_URL", "http://127.0.0.1:9222"),
        help="Chrome CDP endpoint. The pipeline automatically starts its dedicated Chrome profile if needed.",
    )
    parser.add_argument(
        "--no-chrome-auto-launch",
        action="store_true",
        help="Do not start dedicated Chrome automatically; require an already-running CDP browser.",
    )
    parser.add_argument(
        "--chrome-auto-user-data-dir",
        default=os.getenv(
            "SOCIAL_AUTOMATION_CHROME_AUTO_USER_DATA_DIR",
            str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "social-automation-chrome"),
        ),
        help="Persistent dedicated Chrome User Data directory used by automatic CDP launch.",
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
        chrome_auto_launch=not args.no_chrome_auto_launch,
        chrome_auto_user_data_dir=Path(args.chrome_auto_user_data_dir) if args.chrome_auto_user_data_dir else None,
    )

    pipeline = ImageGenerationPipeline(config)
    try:
        result = pipeline.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except GoogleAIModeDailyLimitError as exc:
        print()
        print("=" * 78)
        print("GOOGLE AI MODE DAILY LIMIT REACHED")
        print("=" * 78)
        print(str(exc))
        print()
        print("Action required:")
        print("1. Switch/sign in to another Google account in the dedicated Chrome window.")
        print("2. Confirm Google AI Mode is available.")
        print("3. Run the same pipeline command again.")
        print()
        print("Completed scenes are preserved. The current scene is marked RETRY and")
        print("will resume after you change accounts.")
        return 2
    except KeyboardInterrupt:
        print("Interrupted. SQLite state preserves completed scenes; rerun to resume.")
        return 130
    finally:
        pipeline.close()


if __name__ == "__main__":
    raise SystemExit(main())
