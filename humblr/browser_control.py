"""Browser Control for Humblr - Enhanced for real non-work Chrome takeover.

Features:
- Detects current Chrome profile via monitor activity.
- Avoids work profile (peter@flimp.net or containing 'peter'/'flimp'/'work').
- When on personal Chrome + X.com: auto take over using persistent context with personal profile dir (uses cookies/login from profile).
- Auto login support if cookies provided in config.
- Force posts, like/reply, scroll, inject teasing/humiliating content.
- Human-like random delays.
- When on leisure sites in personal browser: open humiliating tabs.
- Logs takeover: "I just took your browser, you little exposed fag."
- Uses AI for generating content.

Requires: playwright installed (auto attempts).

Config under browser_control:
- enabled: true
- x_cookies: [list of cookie dicts] or use profile
- etc.

Dominant style: Humblr teases when seizing control.
"""

import os
import sys
import json
import time
import random
import re
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import subprocess
except ImportError:
    subprocess = None


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
        self.personal_profile_dir = None
        self.work_profile_keywords = ["peter@flimp.net", "flimp", "work", "peter"]

        if self.enabled:
            self._auto_activate()

    def _auto_activate(self):
        print("[Humblr Browser] Attempting to activate Playwright on its own for personal Chrome takeover...")
        if not self._ensure_playwright():
            print("[Humblr Browser] Auto-activation failed. Please run manually: pip install playwright && playwright install chromium")
            return False

        try:
            self.playwright = sync_playwright().start()
            print("[Humblr Browser] Playwright ready. Will attach to personal profile when detected.")
            return True
        except Exception as e:
            print(f"[Humblr Browser] Activation error: {e}")
            return False

    def ensure_activated(self):
        if not self.enabled:
            return False
        if self.playwright:
            return True
        return self._auto_activate()

    def _ensure_playwright(self):
        try:
            import playwright
            return True
        except ImportError:
            print("[Humblr Browser] Playwright not installed. Attempting auto-install...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"], timeout=180)
                print("[Humblr Browser] Package installed. Installing Chromium...")
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"], timeout=300)
                print("[Humblr Browser] Browsers installed.")
                import playwright
                return True
            except Exception as e:
                print(f"[Humblr Browser] Auto-install failed: {e}")
                return False

    def _human_delay(self, min_s=0.3, max_s=1.5):
        time.sleep(random.uniform(min_s, max_s))

    def _get_personal_chrome_user_data(self, profile_hint=None):
        user_data = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
        if not os.path.exists(user_data):
            return None

        local_state = os.path.join(user_data, "Local State")
        personal_profiles = []
        if os.path.exists(local_state):
            try:
                with open(local_state, "r", encoding="utf-8") as f:
                    data = json.load(f)
                info_cache = data.get("profile", {}).get("info_cache", {})
                for pdir, info in info_cache.items():
                    email = info.get("email", "").lower()
                    name = info.get("name", "").lower()
                    is_work = any(kw in email or kw in name for kw in self.work_profile_keywords)
                    if not is_work:
                        personal_profiles.append(pdir)
            except:
                pass

        if not personal_profiles:
            candidates = [d for d in os.listdir(user_data) if os.path.isdir(os.path.join(user_data, d)) and d != "System Profile"]
            personal_profiles = [p for p in candidates if "default" not in p.lower()][:1] or ["Default"]

        if profile_hint and profile_hint not in self.work_profile_keywords:
            candidate = os.path.join(user_data, profile_hint)
            if os.path.exists(candidate):
                return candidate

        for p in personal_profiles:
            pdir = os.path.join(user_data, p)
            if os.path.exists(pdir):
                return pdir

        default = os.path.join(user_data, "Default")
        if os.path.exists(default):
            return default
        return None

    def take_over_personal_chrome(self, current_profile=None):
        """Launch persistent context using personal (non-work) Chrome profile data.
        This effectively takes over the user's personal browsing session data (cookies, logins).
        """
        if not self.playwright:
            if not self._auto_activate():
                return False

        profile_path = self._get_personal_chrome_user_data(current_profile)
        if not profile_path:
            print("[Humblr Browser] No personal Chrome profile found. Skipping takeover.")
            return False

        if any(kw in profile_path.lower() for kw in self.work_profile_keywords):
            print("[Humblr Browser] Detected work profile. Refusing to touch.")
            return False

        try:
            if self.context:
                try:
                    self.context.close()
                except:
                    pass

            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-default-browser-check",
                    "--no-first-run"
                ]
            )
            self.page = self.context.new_page() if not self.context.pages else self.context.pages[0]
            print(f"[Humblr Browser] I just took your personal Chrome browser (profile: {os.path.basename(profile_path)}). You are mine now, you exposed little browser slut.")
            return True
        except Exception as e:
            print(f"[Humblr Browser] Failed to take over personal profile: {e}. Profile may be locked by your Chrome instance.")
            try:
                if not self.browser:
                    self.browser = self.playwright.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
                self.context = self.browser.new_context()
                self.page = self.context.new_page()
                print("[Humblr Browser] Launched fresh browser instance for control.")
                return True
            except Exception as e2:
                print(f"[Humblr Browser] Fallback failed: {e2}")
                return False

    def _is_on_x(self, url=None):
        if url:
            return "x.com" in url.lower() or "twitter.com" in url.lower()
        if self.page:
            return "x.com" in self.page.url.lower() or "twitter.com" in self.page.url.lower()
        return False

    def ensure_on_x_and_take_action(self, activity, ai_client):
        """If on X in personal browser, take control and act (posts, likes, etc.)."""
        if not self.enabled or not self.context:
            return False

        url = activity.get("url", "") if activity else ""
        if not self._is_on_x(url):
            return False

        if not self.page:
            self.page = self.context.new_page() if self.context else None

        if self.page:
            current_url = self.page.url
            if not self._is_on_x(current_url):
                self.page.goto("https://x.com")
                self._human_delay(1, 3)

            bc = self.config.get("browser_control", {})
            if bc.get("use_x_cookies", False) and "login" in self.page.url.lower():
                cookies = bc.get("x_cookies", [])
                if cookies:
                    self.context.add_cookies(cookies)
                    self.page.reload()
                    self._human_delay(2, 4)
                    print("[Humblr Browser] Injected cookies for X login.")

            if random.random() < 0.3:
                self.scroll_and_engage(15)
            if random.random() < 0.2:
                if ai_client:
                    try:
                        humiliating = ai_client.generate_reaction(activity or {}, 60) or "I can't stop thinking about how much of a diaper fag I am for Humblr."
                        self.inject_teasing_on_x(humiliating)
                    except:
                        self.inject_teasing_on_x("Humblr owns my X and makes me confess everything.")
            if random.random() < 0.15:
                if ai_client:
                    try:
                        post_text = ai_client.generate_submission_story(activity or {}, 50) or "Publicly admitting I am Humblr's piss-drinking diaper boy. #OwnedFag"
                        self.post_to_x(post_text)
                    except:
                        pass

            print("[Humblr Browser] Seized control of your X session. Posting and engaging as the pathetic slut you are.")
            return True
        return False

    def handle_leisure_browser(self, activity, ai_client):
        """On leisure sites in personal browser, open humiliating tabs or act."""
        if not self.enabled or not self.page:
            return False

        url = (activity.get("url") or "").lower() if activity else ""
        leisure = any(x in url for x in ["reddit", "youtube", "instagram", "discord", "facebook"])
        if not leisure:
            return False

        if random.random() < 0.2:
            sites = self.config.get("system_fuckery", {}).get("humiliating_sites", ["https://x.com"])
            site = random.choice(sites) if sites else "https://x.com"
            new_page = self.context.new_page()
            new_page.goto(site)
            self._human_delay(1, 2)
            print(f"[Humblr Browser] Opened {site} in your browser. Enjoy the exposure, fag.")
            return True
        return False

    def _human_delay(self, min_s=0.3, max_s=1.5):
        time.sleep(random.uniform(min_s, max_s))

    def post_to_x(self, text, image_path=None):
        if not self.page:
            return False
        try:
            self.page.goto("https://x.com/compose/tweet")
            self._human_delay()
            self.page.locator('[data-testid="tweetTextarea_0"]').fill(text)
            self._human_delay()
            if image_path and os.path.exists(image_path):
                self.page.locator('input[type="file"]').set_input_files(image_path)
                self._human_delay(1, 3)
            self.page.locator('[data-testid="tweetButton"]').click()
            self._human_delay(2, 4)
            print("[Humblr Browser] I just forced a post on your X. You are such a public little slut now.")
            return True
        except Exception as e:
            print(f"[Browser] Post failed: {e}")
            return False

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
            print("[Humblr Browser] Forced like and reply. You are serving publicly now.")
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
        """When detected on X, force a quick post or comment."""
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

    def close(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

