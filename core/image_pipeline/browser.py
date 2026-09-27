from __future__ import annotations
import os,re,subprocess,time,urllib.request,urllib.error
from pathlib import Path
from .models import PipelineConfig
class BrowserAutomationError(RuntimeError): pass
class BrowserBlockedError(BrowserAutomationError): pass
class GoogleAIModeDailyLimitError(BrowserBlockedError): pass
class GoogleAIModeBrowser:
    def __init__(self,config): self.config=config; self.playwright=self.browser=self.context=self.page=None; self.remote=False; self.proc=None
    def start(self):
        try: from playwright.sync_api import sync_playwright
        except Exception as e: raise BrowserAutomationError("Playwright is required") from e
        self.playwright=sync_playwright().start()
        if self.config.chrome_cdp_url:
            if self.config.chrome_auto_launch and not self._cdp_ready(): self._launch_chrome()
            try:self.browser=self.playwright.chromium.connect_over_cdp(self.config.chrome_cdp_url)
            except Exception as e: raise BrowserAutomationError(f"cannot connect to Chrome CDP {self.config.chrome_cdp_url}") from e
            self.remote=True; self.context=self.browser.contexts[0] if self.browser.contexts else self.browser.new_context(); self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
        else:
            self.context=self.playwright.chromium.launch_persistent_context(str(self.config.output_dir/"chrome_profile"),channel="chrome",headless=False,accept_downloads=True); self.page=self.context.pages[0]
        self.page.set_default_timeout(self.config.page_timeout_ms); self.page.goto("https://www.google.com/ai",wait_until="domcontentloaded",timeout=self.config.page_timeout_ms); self._check_blocked(); self._ensure_prompt()
    def _cdp_ready(self):
        try:
            with urllib.request.urlopen(self.config.chrome_cdp_url.rstrip("/")+"/json/version",timeout=1.5) as r:return r.status==200
        except (OSError,urllib.error.URLError):return False
    def _launch_chrome(self):
        exe=os.path.join(os.environ.get("PROGRAMFILES",""),"Google","Chrome","Application","chrome.exe"); exe=exe if Path(exe).exists() else os.path.join(os.environ.get("LOCALAPPDATA",""),"Google","Chrome","Application","chrome.exe")
        if not Path(exe).exists(): raise BrowserAutomationError("Chrome executable not found")
        from urllib.parse import urlparse
        u=urlparse(self.config.chrome_cdp_url); profile=self.config.chrome_auto_user_data_dir or Path(os.environ.get("LOCALAPPDATA",Path.home()))/"social-automation-chrome"; profile.mkdir(parents=True,exist_ok=True)
        self.proc=subprocess.Popen([exe,f"--remote-debugging-address={u.hostname or '127.0.0.1'}",f"--remote-debugging-port={u.port or 9222}",f"--user-data-dir={profile}","--no-first-run","--no-default-browser-check","https://www.google.com/ai"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.time()+20
        while time.time()<deadline:
            if self._cdp_ready(): return
            if self.proc.poll() is not None: break
            time.sleep(.25)
        raise BrowserAutomationError("Chrome CDP did not become ready")
    def _body(self):
        try:return self.page.locator("body").inner_text(timeout=5000).lower()
        except Exception:return ""
    def _check_blocked(self):
        t=self._body()
        if any(x in t for x in ("daily limit","try again tomorrow")): raise GoogleAIModeDailyLimitError("Google AI Mode daily image-generation limit reached")
        if any(x in t for x in ("unusual traffic","verify you are human","captcha")): raise BrowserBlockedError("Google requires human intervention")
    def _prompt_box(self):
        for sel in ['textarea[placeholder*="Ask anything" i]','[contenteditable="true"][aria-label*="Ask" i]','textarea','[contenteditable="true"]']:
            try:
                loc=self.page.locator(sel).first
                if loc.count() and loc.is_visible(): return loc
            except Exception: pass
        return None
    def _ensure_prompt(self):
        if self._prompt_box() is None: raise BrowserAutomationError("Google AI Mode prompt box not found")
    def _select_create_images(self):
        patterns=[r"^Create Images$",r"^Create image$"]
        try:
            image=self.page.get_by_role("button",name=re.compile(r"^Image$|Images",re.I)).first
            if image.count() and image.is_visible():
                image.click(); time.sleep(.7)
                for p in patterns:
                    loc=self.page.get_by_text(re.compile(p,re.I)).first
                    if loc.count() and loc.is_visible(): loc.click(); time.sleep(.7); return True
        except Exception: pass
        for p in patterns:
            try:
                loc=self.page.get_by_text(re.compile(p,re.I)).first
                if loc.count() and loc.is_visible(): loc.click(); time.sleep(.7); return True
            except Exception: pass
        return False
    def _images(self):
        try:return set(self.page.locator("img").evaluate_all("""els=>els.map(e=>[e.currentSrc||e.src||'',e.naturalWidth||0,e.naturalHeight||0]).filter(x=>x[1]>=200&&x[2]>=200).map(x=>x.join('|'))"""))
        except Exception:return set()
    def generate(self,*,prompt,destination,previous_image=None):
        if not self._select_create_images(): raise BrowserAutomationError("Could not select Google's Create Images mode. No prompt was submitted.")
        box=self._prompt_box()
        if box is None: raise BrowserAutomationError("Google AI Mode prompt box disappeared")
        before=self._images(); box.click(); box.fill(prompt); box.press("Enter"); deadline=time.time()+self.config.generation_timeout_s
        while time.time()<deadline:
            self._check_blocked(); now=self._images()
            if now-before:
                for i in range(self.page.locator("img").count()-1,-1,-1):
                    loc=self.page.locator("img").nth(i)
                    try:
                        info=loc.evaluate("e=>({src:e.currentSrc||e.src||'',nw:e.naturalWidth||0,nh:e.naturalHeight||0})")
                        if info["nw"]>=200 and info["nh"]>=200 and info["src"]:
                            data=urllib.request.urlopen(info["src"],timeout=20).read(); destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(data); return {"status":"generated","source":"google_ai_mode"}
                    except Exception: continue
            time.sleep(2)
        raise BrowserAutomationError("Timed out waiting for a generated image")
    def recover(self):
        try:self.page.reload(wait_until="domcontentloaded",timeout=self.config.page_timeout_ms)
        except Exception:pass
    def close(self):
        try:
            if self.context and not self.remote:self.context.close()
        finally:
            if self.playwright:self.playwright.stop()
            self.page=self.context=self.browser=self.playwright=None
