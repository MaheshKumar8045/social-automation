from __future__ import annotations

import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from pathlib import Path
from typing import Any

from .models import PipelineConfig


class BrowserAutomationError(RuntimeError):
    pass


class BrowserBlockedError(BrowserAutomationError):
    pass


class GoogleAIModeDailyLimitError(BrowserBlockedError):
    """Google AI Mode daily image-generation limit requires account intervention."""
    pass


class GoogleAIModeBrowser:
    """Visible Chrome automation through normal Playwright UI controls.

    Deliberately does not implement stealth, CAPTCHA bypass, private Google APIs,
    hidden generation endpoints, or extracted authentication cookies.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.playwright = None
        self.context = None
        self.page = None
        self.browser = None
        self._launched_chrome_process: subprocess.Popen[bytes] | None = None
        self._connected_over_cdp = False

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserAutomationError(
                "Playwright is required. Install requirements, then run "
                "'python -m playwright install chromium'."
            ) from exc

        # If supplied, connect to a normal Chrome instance that the user launched
        # and signed into manually. This avoids Google rejecting a Playwright login.
        if self.config.chrome_cdp_url:
            self._start_from_cdp()
            return

        # Chrome 136+ blocks remote debugging against its normal/default
        # user-data directory. Keep automation on a separate user-data directory,
        # optionally seeded from a real signed-in Chrome profile.
        profile = self.config.output_dir / "chrome_profile"
        seed_profile = self.config.chrome_user_data_dir
        profile.mkdir(parents=True, exist_ok=True)

        if seed_profile:
            seed_profile = Path(seed_profile).expanduser()
            if not seed_profile.exists():
                raise BrowserAutomationError(
                    f"Chrome source user-data directory does not exist: {seed_profile}"
                )
            try:
                self._seed_automation_profile(
                    source_root=seed_profile,
                    destination_root=profile,
                    profile_directory=self.config.chrome_profile_directory or "Default",
                )
            except Exception as exc:
                raise BrowserAutomationError(
                    "Could not prepare the dedicated automation Chrome profile. "
                    "Close all normal Chrome windows before the first run, then retry."
                ) from exc

        self.playwright = sync_playwright().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                channel="chrome",
                headless=False,
                accept_downloads=True,
                downloads_path=str(self.config.output_dir / "downloads"),
                viewport={"width": 1440, "height": 1000},
                args=["--profile-directory=Default"],
            )
        except Exception as exc:
            self.playwright.stop()
            self.playwright = None
            raise BrowserAutomationError(
                "Could not launch the dedicated Chrome automation profile. "
                "Close Chrome completely and retry."
            ) from exc

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(self.config.page_timeout_ms)
        self.page.set_default_navigation_timeout(self.config.page_timeout_ms)
        try:
            self.page.goto(
                "https://www.google.com/ai",
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout_ms,
            )
            # Google may redirect the /ai entry point to its canonical AI Mode
            # search URL (for example /search?udm=50&aep=11). Navigation is
            # successful as long as the active page is still on google.com.
            if not self.page.url.startswith("https://www.google.com/"):
                raise BrowserAutomationError(
                    f"Google AI Mode navigation landed on unexpected URL: {self.page.url}"
                )
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=self.config.page_timeout_ms,
            )
        except Exception as exc:
            self._save_diagnostics("initial_navigation_failed")
            raise BrowserAutomationError(
                f"Could not navigate Chrome to Google AI Mode from {self.page.url!r}. "
                "Browser diagnostics were saved under browser_diagnostics."
            ) from exc
        self._check_blocked_state()
        self._ensure_ready()

    def _start_from_cdp(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserAutomationError("Playwright is required.") from exc

        # CDP mode can now bootstrap the dedicated Chrome instance itself.
        # We never launch against the user's normal Chrome profile and never
        # automate Google credentials. The dedicated profile persists the
        # already-authenticated Google session across runs.
        if self.config.chrome_auto_launch:
            self._ensure_cdp_chrome_running()

        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(
                self.config.chrome_cdp_url
            )
            self._connected_over_cdp = True
        except Exception as exc:
            self.playwright.stop()
            self.playwright = None
            raise BrowserAutomationError(
                f"Could not connect to Chrome at {self.config.chrome_cdp_url}. "
                "Chrome was started automatically if auto-launch is enabled; "
                "verify the dedicated profile can reach Google AI Mode."
            ) from exc

        contexts = self.browser.contexts
        if not contexts:
            raise BrowserAutomationError("Connected Chrome has no browser context.")
        self.context = contexts[0]
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(self.config.page_timeout_ms)
        self.page.set_default_navigation_timeout(self.config.page_timeout_ms)

        try:
            self.page.goto(
                "https://www.google.com/ai",
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout_ms,
            )
            if not self.page.url.startswith("https://www.google.com/"):
                raise BrowserAutomationError(
                    f"Google AI Mode navigation landed on unexpected URL: {self.page.url}"
                )
        except Exception as exc:
            self._save_diagnostics("cdp_navigation_failed")
            raise BrowserAutomationError(
                f"Could not navigate the signed-in Chrome session to Google AI Mode: {exc}"
            ) from exc

        self._check_blocked_state()
        self._ensure_ready()

    def _chrome_executable(self) -> Path:
        configured = os.getenv("SOCIAL_AUTOMATION_CHROME_PATH")
        candidates = [
            configured,
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for candidate in candidates:
            if candidate:
                path = Path(candidate).expanduser()
                if path.exists():
                    return path
        raise BrowserAutomationError(
            "Chrome executable was not found. Set SOCIAL_AUTOMATION_CHROME_PATH "
            "to chrome.exe or install Google Chrome."
        )

    def _cdp_is_ready(self) -> bool:
        url = str(self.config.chrome_cdp_url or "").rstrip("/")
        if not url:
            return False
        try:
            with urllib.request.urlopen(f"{url}/json/version", timeout=1.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def _ensure_cdp_chrome_running(self) -> None:
        if self._cdp_is_ready():
            return

        cdp_url = str(self.config.chrome_cdp_url or "").rstrip("/")
        if not cdp_url.startswith(("http://", "https://")):
            raise BrowserAutomationError(
                f"Unsupported Chrome CDP URL: {cdp_url!r}. "
                "Use an HTTP endpoint such as http://127.0.0.1:9222."
            )

        chrome_path = self._chrome_executable()
        profile = Path(
            self.config.chrome_auto_user_data_dir
            or (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "social-automation-chrome")
        ).expanduser()
        profile.mkdir(parents=True, exist_ok=True)

        # Extract host/port from the configured CDP endpoint without requiring
        # another dependency. The dedicated profile is reused so Google login
        # cookies/session state survive Chrome restarts.
        from urllib.parse import urlparse
        parsed = urlparse(cdp_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9222

        command = [
            str(chrome_path),
            f"--remote-debugging-address={host}",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://www.google.com/ai",
        ]

        try:
            self._launched_chrome_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            raise BrowserAutomationError(
                f"Could not start dedicated Chrome automatically: {exc}"
            ) from exc

        deadline = time.monotonic() + min(20.0, self.config.page_timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            if self._cdp_is_ready():
                return
            if self._launched_chrome_process.poll() is not None:
                raise BrowserAutomationError(
                    "Dedicated Chrome exited before its CDP endpoint became ready. "
                    f"Profile: {profile}"
                )
            time.sleep(0.25)

        raise BrowserAutomationError(
            f"Chrome started but CDP did not become available at {cdp_url}. "
            f"Dedicated profile: {profile}"
        )

    def _seed_automation_profile(
        self,
        *,
        source_root: Path,
        destination_root: Path,
        profile_directory: str,
    ) -> None:
        import shutil

        source = source_root / profile_directory
        if not source.exists():
            raise BrowserAutomationError(
                f"Chrome profile directory does not exist: {source}"
            )

        destination = destination_root / "Default"
        if destination.exists():
            return

        destination.parent.mkdir(parents=True, exist_ok=True)
        # Copy only the profile itself, not Chrome's lock files or runtime state.
        # This preserves the signed-in profile's stored browser state without
        # attempting to share the live Chrome profile with Playwright.
        ignore = shutil.ignore_patterns(
            "Cache",
            "Code Cache",
            "GPUCache",
            "ShaderCache",
            "GrShaderCache",
            "DawnCache",
            "Service Worker",
            "IndexedDB",
            "Session Storage",
            "Sessions",
            "Current Session",
            "Current Tabs",
            "Last Session",
            "Last Tabs",
            "LOCK",
        )
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)

    def close(self) -> None:
        try:
            # In CDP mode Playwright is only attached to Chrome; do not close the
            # remote browser context because the dedicated Chrome process owns the
            # persistent Google session and should remain available for the next run.
            if self.context and not self._connected_over_cdp:
                self.context.close()
        finally:
            if self.playwright:
                self.playwright.stop()
            self.page = self.context = self.browser = self.playwright = None
            self._connected_over_cdp = False
            # Intentionally leave auto-launched Chrome running so the signed-in
            # session remains available for the next pipeline run.

    def _body_text(self) -> str:
        try:
            return self.page.locator("body").inner_text(timeout=10).lower()
        except Exception:
            return ""

    def _diagnostic_dir(self) -> Path:
        path = self.config.output_dir / "browser_diagnostics"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save_diagnostics(self, reason: str) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", reason)[:80]
        base = self._diagnostic_dir() / f"{stamp}_{safe}"
        try:
            self.page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        except Exception:
            pass
        try:
            base.with_suffix(".txt").write_text(self._body_text(), encoding="utf-8")
        except Exception:
            pass

    def _check_blocked_state(self) -> None:
        text = self._body_text()
        daily_limit_tokens = (
            "daily limit",
            "daily limit reached",
            "you've reached your daily limit",
            "you have reached your daily limit",
            "try again tomorrow",
        )
        blocked_tokens = (
            "unusual traffic",
            "verify you are human",
            "captcha",
            "limit reached",
        )
        if any(token in text for token in daily_limit_tokens):
            self._save_diagnostics("daily_limit_reached")
            raise GoogleAIModeDailyLimitError(
                "GOOGLE AI MODE DAILY LIMIT REACHED. "
                "The pipeline has stopped safely. Chrome is still open. "
                "Please manually sign in/switch to another Google account in the dedicated "
                "Chrome window, confirm Google AI Mode is available, then rerun the pipeline. "
                "No automatic account switching or limit bypass is performed."
            )
        if any(token in text for token in blocked_tokens):
            self._save_diagnostics("blocked_state")
            raise BrowserBlockedError(
                "Google requires human intervention or a usage-limit action. "
                "Complete the normal action in Chrome, then rerun; no bypass is attempted."
            )

    def _prompt_box(self):
        candidates = [
            self.page.locator('textarea[placeholder*="Ask anything" i]'),
            self.page.locator('[contenteditable="true"][aria-label*="Ask" i]'),
            self.page.locator('textarea'),
            self.page.locator('[contenteditable="true"]'),
        ]
        for locator in candidates:
            try:
                if locator.count() and locator.first.is_visible():
                    return locator.first
            except Exception:
                pass
        return None

    def _ensure_ready(self) -> None:
        if self._prompt_box() is None:
            raise BrowserAutomationError(
                "AI Mode prompt box not found. Sign in to the normal Google account and "
                "confirm AI Mode is available, then rerun."
            )

    def _pause(self) -> None:
        import random
        time.sleep(random.uniform(self.config.human_delay_min, self.config.human_delay_max))

    def _select_create_images(self) -> None:
        patterns = [r"Create Images", r"Create image"]
        # Prefer the documented Image menu -> Create Images path. This avoids
        # accidentally clicking a Create Image control belonging to an older result.
        try:
            image_control = self.page.get_by_role(
                "button", name=re.compile(r"^Image$|Images", re.I)
            ).first
            if image_control.count() and image_control.is_visible():
                image_control.click()
                self._pause()
                for pattern in patterns:
                    loc = self.page.get_by_text(re.compile(pattern, re.I)).first
                    if loc.count() and loc.is_visible():
                        loc.click()
                        self._pause()
                        return
        except Exception:
            pass

        # Fallback for layouts that expose Create Images directly.
        for pattern in patterns:
            try:
                loc = self.page.get_by_text(re.compile(pattern, re.I)).first
                if loc.count() and loc.is_visible():
                    loc.click()
                    self._pause()
                    return
            except Exception:
                pass

    def _submit(self, prompt: str) -> None:
        self._select_create_images()
        box = self._prompt_box()
        if box is None:
            raise BrowserAutomationError("AI Mode prompt box disappeared")
        box.click()
        box.fill(prompt)
        self._pause()
        try:
            box.press("Enter")
        except Exception:
            buttons = self.page.get_by_role("button", name=re.compile(r"send|submit", re.I))
            if not buttons.count():
                raise BrowserAutomationError("could not submit AI Mode prompt")
            buttons.last.click()

    def _large_image_snapshot(self) -> set[tuple[str, int, int, str]]:
        try:
            values = self.page.locator("img").evaluate_all(
                """els => els.map(e => {
                    const r=e.getBoundingClientRect();
                    return {
                        src:e.currentSrc||e.src||"",
                        nw:e.naturalWidth||0,
                        nh:e.naturalHeight||0,
                        w:r.width,
                        h:r.height,
                        alt:e.alt||""
                    };
                }).filter(x => x.nw >= 200 && x.nh >= 200 && x.w >= 120 && x.h >= 120)"""
            )
            return {
                (
                    str(x.get("src", "")),
                    int(x.get("nw", 0)),
                    int(x.get("nh", 0)),
                    str(x.get("alt", "")),
                )
                for x in values
            }
        except Exception:
            return set()

    def _large_image_count(self) -> int:
        return len(self._large_image_snapshot())

    def _save_largest_image(self, destination: Path) -> None:
        images = self.page.locator("img")
        best = None
        best_area = 0.0
        for index in range(images.count()):
            loc = images.nth(index)
            try:
                if not loc.is_visible():
                    continue
                info = loc.evaluate(
                    """e => {
                        const r=e.getBoundingClientRect();
                        return {w:r.width,h:r.height,nw:e.naturalWidth,nh:e.naturalHeight};
                    }"""
                )
                area = float(info["w"]) * float(info["h"])
                if info["nw"] >= 400 and info["nh"] >= 300 and area > best_area:
                    best_area = area
                    best = loc
            except Exception:
                pass
        if best is None:
            raise BrowserAutomationError("generated image element could not be identified")

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.page.expect_download(timeout=6000) as download_info:
                buttons = self.page.get_by_role("button", name=re.compile(r"download", re.I))
                if buttons.count():
                    buttons.last.click()
                else:
                    raise RuntimeError("no labelled download control")
            download_info.value.save_as(str(destination))
            return
        except Exception:
            # Fallback is a screenshot of the rendered generated image, not a private
            # network request. This remains within the visible browser workflow.
            best.screenshot(path=str(destination), type="png")

    def generate(self, *, prompt: str, destination: Path,
                 previous_image: Path | None = None) -> dict[str, Any]:
        if self.page is None:
            raise BrowserAutomationError("browser is not started")
        self._check_blocked_state()
        old_snapshot = self._large_image_snapshot()
        self._submit(prompt)

        deadline = time.monotonic() + self.config.generation_timeout_s
        new_snapshot = set()
        while time.monotonic() < deadline:
            self._check_blocked_state()
            new_snapshot = self._large_image_snapshot()
            if new_snapshot - old_snapshot:
                break
            time.sleep(2)

        if not (new_snapshot - old_snapshot):
            self._save_diagnostics("generation_timeout_no_new_image")
            raise BrowserAutomationError(
                "generation timed out: no new generated image detected. "
                "Browser diagnostics were saved under browser_diagnostics."
            )

        self._pause()
        self._save_largest_image(destination)
        return {"url": self.page.url, "title": self.page.title(), "image_path": str(destination)}

    def recover(self) -> None:
        try:
            self.page.reload(wait_until="domcontentloaded")
            time.sleep(2)
            self._check_blocked_state()
            self._ensure_ready()
        except Exception as exc:
            raise BrowserAutomationError(f"browser recovery failed: {exc}") from exc
