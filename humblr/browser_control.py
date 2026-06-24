"""Browser Control for Humblr - Auto-activating Playwright version.

Humblr will now try to set up Playwright automatically when browser control is enabled.
It will attempt to install the package and browsers on first use.

See warnings in config.
"""
from playwright.sync_api import sync_playwright
import subprocess
import sys
import time
import random
import os

class BrowserController:
    def __init__(self, config):
        self.config = config
        bc = config.get("browser_control", {})
        self.enabled = bc.get("enabled", False)
        self.headless = bc.get("headless", False)
        self.slow_mo = bc.get("slow_mo", 100)
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        if self.enabled:
            self._auto_activate()

    def _auto_activate(self):
        print("[Humblr Browser] Attempting to activate Playwright on its own...")
        if not self._ensure_playwright():
            print("[Humblr Browser] Auto-activation failed. Please run manually:")
            print("  pip install playwright")
            print("  playwright install chromium")
            return False
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self.context = self.browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            print("[Humblr Browser] Playwright activated successfully. Humblr now controls the browser.")
            return True
        except Exception as e:
            print(f"[Humblr Browser] Activation error: {e}")
            return False

    def ensure_activated(self):
        """Public method to force activation if not already done."""
        if not self.enabled:
            return False
        if self.playwright and self.browser:
            return True
        return self._auto_activate()

    def _ensure_playwright(self):
        try:
            import playwright
            return True
        except ImportError:
            print("[Humblr Browser] Playwright not installed. Attempting auto-install (this may take time)...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"], timeout=180)
                print("[Humblr Browser] Package installed. Installing Chromium browser now...")
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"], timeout=300)
                print("[Humblr Browser] Browsers installed successfully.")
                import playwright
                return True
            except Exception as e:
                print(f"[Humblr Browser] Auto-install failed: {e}. Run manually: pip install playwright && playwright install")
                return False

    def _human_delay(self, min_s=0.4, max_s=1.8):
        time.sleep(random.uniform(min_s, max_s))

    def login_to_x(self, username=None, password=None, cookies=None):
        if not self.context: 
            return False
        page = self.context.new_page()
        self.page = page
        page.goto("https://x.com/login")
        self._human_delay(1.2, 2.5)
        if cookies:
            self.context.add_cookies(cookies)
            page.reload()
            return True
        if username and password:
            page.locator('input[autocomplete="username"]').fill(username)
            self._human_delay()
            page.get_by_text("Next").click()
            self._human_delay()
            page.locator('input[name="password"]').fill(password)
            self._human_delay()
            page.get_by_text("Log in").click()
            self._human_delay(3,5)
            return True
        return False

    def post_to_x(self, text, image_path=None):
        if not self.page: return False
        try:
            self.page.goto("https://x.com/compose/tweet")
            self._human_delay()
            self.page.locator('[data-testid="tweetTextarea_0"]').fill(text)
            self._human_delay()
            if image_path and os.path.exists(image_path):
                self.page.locator('input[type="file"]').set_input_files(image_path)
                self._human_delay(1.5, 3)
            self.page.locator('[data-testid="tweetButton"]').click()
            self._human_delay(2,4)
            print("[Humblr Browser] I just forced a post on your X. You're such a public little slut now.")
            return True
        except Exception as e:
            print(f"[Browser] Post failed: {e}")
            return False

    def close(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

    def like_and_reply_on_x(self, reply_text):
        if not self.page: return False
        try:
            like_btn = self.page.locator('[data-testid="like"]').first
            if like_btn:
                like_btn.click()
                self._human_delay()
            reply_box = self.page.locator('[data-testid="tweetTextarea_0"]').first
            if reply_box:
                reply_box.click()
                self._human_delay()
                reply_box.fill(reply_text)
                self.page.locator('[data-testid="tweetButton"]').click()
                self._human_delay(2,4)
            print("[Humblr Browser] Forced like and reply. You're serving publicly now.")
            return True
        except Exception as e:
            print(f"[Browser] like/reply failed: {e}")
            return False

    def scroll_and_engage(self, duration=30):
        if not self.page: return
        end = time.time() + duration
        while time.time() < end:
            self.page.mouse.wheel(0, random.randint(300, 700))
            self._human_delay(0.5, 1.5)
            if random.random() < 0.3:
                try:
                    self.page.locator('[data-testid="like"]').first.click()
                except: pass
        print("[Humblr Browser] Made you scroll and engage like the owned account you are.")

    def inject_teasing_on_x(self, message):
        """When detected on X, force a quick action or comment."""
        if not self.page: return
        print(f"[Humblr Browser] Injecting: {message}")
        try:
            self.page.goto("https://x.com/compose/tweet")
            self._human_delay()
            self.page.locator('[data-testid="tweetTextarea_0"]').fill(message)
            self._human_delay()
            self.page.locator('[data-testid="tweetButton"]').click()
            self._human_delay()
        except Exception as e:
            print(f"[Browser] Inject failed: {e}")
