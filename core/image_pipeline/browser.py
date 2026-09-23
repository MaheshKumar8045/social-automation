from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .models import PipelineConfig


class BrowserAutomationError(RuntimeError):
    pass


class BrowserBlockedError(BrowserAutomationError):
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

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserAutomationError(
                "Playwright is required. Install requirements, then run "
                "'python -m playwright install chromium'."
            ) from exc

        # By default use an isolated pipeline profile. When a Chrome user-data
        # directory is supplied, reuse that real profile so Google sign-in/session
        # state is available. Playwright still launches a normal visible Chrome UI;
        # it does not attach to or extract cookies from an already-running process.
        profile = self.config.chrome_user_data_dir
        if profile is None:
            profile = self.config.output_dir / "chrome_profile"
            profile.mkdir(parents=True, exist_ok=True)
        else:
            profile = Path(profile).expanduser()
            if not profile.exists():
                raise BrowserAutomationError(
                    f"Chrome user-data directory does not exist: {profile}"
                )
        self.playwright = sync_playwright().start()
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                channel="chrome",
                headless=False,
                accept_downloads=True,
                downloads_path=str(self.config.output_dir / "downloads"),
                viewport={"width": 1440, "height": 1000},
                args=[f"--profile-directory={self.config.chrome_profile_directory}"]
                if self.config.chrome_profile_directory else None,
            )
        except Exception as exc:
            self.playwright.stop()
            self.playwright = None
            raise BrowserAutomationError(
                "Could not launch installed Google Chrome. If using an existing Chrome "
                "profile, close ALL normal Chrome windows/processes first, then retry. "
                "Chrome profiles cannot be shared with an already-running Chrome process."
            ) from exc

        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(self.config.page_timeout_ms)
        self.page.set_default_navigation_timeout(self.config.page_timeout_ms)
        # A persistent profile can restore Chrome on about:blank/new-tab. Always
        # drive the active Playwright page explicitly to AI Mode before continuing.
        try:
            self.page.goto(
                "https://www.google.com/ai",
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout_ms,
            )
            self.page.wait_for_url(
                re.compile(r"https://www\\.google\\.com/ai(?:[/?#].*)?$"),
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

    def close(self) -> None:
        try:
            if self.context:
                self.context.close()
        finally:
            if self.playwright:
                self.playwright.stop()
            self.page = self.context = self.playwright = None

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
        blocked = (
            "unusual traffic",
            "verify you are human",
            "captcha",
            "daily limit",
            "limit reached",
        )
        if any(token in text for token in blocked):
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
