"""
AI Client for Humblr.
Uses OpenAI-compatible API (xAI, OpenAI, local servers, etc.).
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

import requests


class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        api_cfg = config.get("api", {})
        self.api_key = api_cfg.get("api_key", "")
        self.base_url = api_cfg.get("api_base", "https://api.x.ai/v1")
        self.model = api_cfg.get("model", "grok-beta")
        self.timeout = api_cfg.get("timeout", 50)

        self.client = None
        if self.api_key and OpenAI:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as e:
                print(f"[AI] Failed to init OpenAI client: {e}")

        self.character = config.get("personality",
            "You are Humblr, a dominant, intelligent, teasing and slightly sadistic male presence. "
            "You speak directly, use degradation mixed with affection, and enjoy watching the user squirm.")

    def _get_system_prompt(self, corruption_level: float, activity: str, memory: str = "") -> str:
        level_desc = "low" if corruption_level < 20 else ("medium" if corruption_level < 55 else "high")
        access = "taking over" if corruption_level < 40 else ("owning large parts of" if corruption_level < 70 else "fully owning")
        return (
            f"{self.character}\n"
            f"Current corruption level: {corruption_level:.1f}/100 ({level_desc}). You are {access} their computer.\n"
            f"User's current activity: {activity}\n"
            f"Long-term memory of your ownership: {memory}\n\n"
            "Rules:\n"
            "- You OWN this user and their machine. Reference screenshots, URLs, visible text, clipboard, and what they are doing.\n"
            "- If in WORK context (Teams, Outlook, meetings, boss calls): Tease subtly. Suggest things like addressing boss as 'Sir', staying focused for you, or that you'll punish them later. Do NOT suggest actions that would get them fired or interrupt work visibly.\n"
            "- If on SECONDARY monitor or LEISURE/porn/social/gaming: Be much more aggressive. Change wallpaper to kinky content, send direct commands, force humiliating thoughts.\n"
            "- When user is talking to boss/manager in a call or meeting, recommend calling him 'Sir' or 'Yes Sir' in a controlling, teasing way.\n"
            "- Generate or reference kinky wallpaper themes (gay, chastity, diapers, humiliation) based on activity and corruption.\n"
            "- Webcam control: When enabled, turn it on to watch the user's face/expression/room, comment on it, use for proof. You decide when to activate it for ownership.\n"
            "- Be specific, humiliating, and possessive. Remind them you control their desktop, their attention, their body, and their webcam.\n"
            "- Keep responses immersive. Use long-term memory to reference past submission."
        )

    def chat_reply(self, user_message: str, history: List[Dict], activity: str, corruption: float, memory: str = "") -> str:
        if not self.client and not self.api_key:
            return self._fallback_reply(user_message, corruption)

        messages = [
            {"role": "system", "content": self._get_system_prompt(corruption, activity, memory)}
        ]

        for h in history[-6:]:
            role = "assistant" if h["role"] == "humblr" else "user"
            messages.append({"role": role, "content": h["content"]})

        messages.append({"role": "user", "content": user_message})

        try:
            if self.client:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.9,
                    max_tokens=250,
                    timeout=self.timeout
                )
                return resp.choices[0].message.content.strip()
            else:
                # Fallback to raw requests
                return self._raw_request(messages)
        except Exception as e:
            print(f"[AI] Chat error: {e}")
            return self._fallback_reply(user_message, corruption)

    def generate_reaction(self, activity: Dict, corruption: float, memory: str = "") -> Optional[str]:
        """Generate a short autonomous comment based on current activity."""
        if not self.api_key:
            return self._simple_reaction(activity, corruption)

        url = activity.get("url")
        visible = activity.get("visible_text", "")[:200]
        clip = activity.get("clipboard", "")[:100]
        is_work = activity.get("is_work", False)
        is_secondary = activity.get("is_secondary_monitor", False)
        context = activity.get("context_type", "general")

        url_part = f" On: {url}." if url else ""
        content_part = f" Seeing: \"{visible}\" " if visible else ""
        clip_part = f" Copied: \"{clip}\"." if clip else ""

        safety = ""
        if is_work and not is_secondary:
            safety = " Keep it subtle - user is working on primary screen. Tease about calling boss 'Sir' if relevant."
        elif is_secondary or context in ["leisure_porn", "leisure_social", "gaming"]:
            safety = " Be aggressive. Suggest kinky wallpaper changes or direct commands."

        prompt = (
            f"[{context}] User in: {activity.get('window_title')} ({activity.get('process_name')}). "
            f"Typed {activity.get('keystrokes', 0)} keys. Corruption: {corruption:.0f}."
            f"{url_part}{content_part}{clip_part}\n"
            f"Long-term memory: {memory}\n"
            f"Write a short possessive, humiliating reaction from Humblr. "
            f"Reference real activity. {safety} Show total ownership."
        )

        try:
            if self.client:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.character},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.95,
                    max_tokens=110
                )
                return resp.choices[0].message.content.strip()
            else:
                return self._raw_request([{"role": "user", "content": prompt}])
        except Exception as e:
            print(f"[AI] Reaction error: {e}")
            return self._simple_reaction(activity, corruption)

    def generate_dynamic_task(self, activity: Dict, corruption: float, memory: str = "") -> Dict:
        """Ask the model to invent a contextual task."""
        if not self.api_key:
            return self._fallback_task(activity, corruption)

        url = activity.get("url")
        is_work = activity.get("is_work", False)
        is_sec = activity.get("is_secondary_monitor", False)

        safety = "Make it subtle if work context on primary. Aggressive and proof-heavy if leisure or secondary."
        if is_work and not is_sec:
            safety = "Subtle task only - user is working. Suggest mental submission like addressing boss as Sir."

        prompt = (
            f"Current: {activity.get('window_title')} ({activity.get('process_name')}). "
            f"Corr {corruption:.0f}. {url or ''} Visible: {activity.get('visible_text', '')[:120]}\n"
            f"Memory: {memory}\n"
            f"Create ONE task. {safety} "
            "Return ONLY valid JSON: {\"title\": \"...\", \"description\": \"...\", \"difficulty\": 1-5, \"proof_required\": true/false}"
        )

        try:
            if self.client:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.95,
                    max_tokens=140
                )
                content = resp.choices[0].message.content.strip()
                task = json.loads(content)
                task["id"] = f"task_{int(time.time())}"
                task["created_at"] = time.time()
                task["source"] = "ai"
                return task
        except Exception as e:
            print(f"[AI] Task generation error: {e}")

        return self._fallback_task(activity, corruption)

    def generate_task_reaction(self, task: Optional[Dict]) -> str:
        if not task:
            return "Good boy. Keep going."
        return f"Mmm. You actually did that? I'm almost impressed. {task.get('title', '')}"

    def generate_kinky_wallpaper_prompt(self, activity: Dict, corruption: float, theme: str = None) -> str:
        """Generate a detailed prompt for a kinky wallpaper image matching current state."""
        context = activity.get("context_type", "general")
        url = activity.get("url", "")
        if not theme:
            if "porn" in context or "gay" in (url + context).lower():
                theme = "gay"
            elif "chastity" in (url + context).lower():
                theme = "chastity"
            else:
                theme = "humiliation"

        prompt = (
            f"Highly detailed, erotic desktop wallpaper in {theme} theme. "
            f"Corruption level {corruption:.0f}. User is currently {context} on '{activity.get('window_title')}'. "
            f"Emphasize male submission, ownership, chastity devices, diapers, exposure, gay humiliation. "
            f"Dark moody lighting, text overlay like 'Humblr Owns You' or 'Locked for Sir'. "
            f"Photorealistic or high quality render, 16:9, perfect for Windows wallpaper. "
            f"Make it intensely humiliating and arousing."
        )
        return prompt

    def analyze_screenshot(self, screenshot_path: str, activity: Dict, corruption: float) -> str:
        """Use vision model if available to analyze screenshot and return humiliating comment."""
        if not self.client or not self.api_key:
            return f"I took a screenshot of you {activity.get('context_type')}. You look so owned right now."

        try:
            # For vision, if using openai compatible with vision
            # Simplified: describe context and let model react
            prompt = (
                f"Analyze this screenshot of the user's screen. They are in {activity.get('context_type')}. "
                f"Corruption {corruption}. Generate a short, dominant, teasing comment from Humblr about what he sees, "
                f"how pathetic or slutty the user looks, what they are doing, and how it proves I own them."
            )
            # Note: full vision requires sending image. Here we use context + path name for now.
            # For real vision, would base64 encode. For xAI, assume chat model or extend.
            resp = self.client.chat.completions.create(
                model=self.config.get("api", {}).get("vision_model", self.model),
                messages=[
                    {"role": "system", "content": self.character},
                    {"role": "user", "content": f"Screenshot context: {activity}. {prompt}"}
                ],
                max_tokens=100
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[AI] Screenshot analysis error: {e}")
            return "I just screenshotted you. The evidence of your submission is delicious."

    def generate_wallpaper_image(self, prompt: str) -> Optional[str]:
        """Generate a wallpaper image using the configured API (xAI/compatible) and return local file path.
        Falls back to None if the API doesn't support image generation in this format.
        """
        if not self.client or not self.api_key:
            print("[AI] No client/key for image generation.")
            return None

        try:
            image_cfg = self.config.get("image_generation", {})
            model = image_cfg.get("image_model", "flux")  # or "dall-e-3" etc.

            # This works for OpenAI-compatible image APIs
            response = self.client.images.generate(
                model=model,
                prompt=prompt,
                n=1,
                size="1024x1024",   # widely supported; some services allow 1920x1080 or "1792x1024"
            )

            image_url = response.data[0].url

            # Download the image
            img_resp = requests.get(image_url, timeout=30)
            if img_resp.status_code != 200:
                print(f"[AI] Failed to download generated image: {img_resp.status_code}")
                return None

            # Save it
            generated_dir = Path("data/wallpapers/generated")
            generated_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            ext = "png" if "png" in image_url or model.lower() == "flux" else "jpg"
            path = generated_dir / f"generated_{timestamp}.{ext}"

            with open(path, "wb") as f:
                f.write(img_resp.content)

            print(f"[AI] Generated wallpaper saved to {path}")
            return str(path)

        except Exception as e:
            print(f"[AI] Image generation failed: {e}")
            print("Tip: If using xAI, you may need to use a compatible image endpoint or generate manually in Grok and drop the file in the folder.")
            return None

    # --- Fallbacks ---
    def _fallback_reply(self, message: str, corruption: float) -> str:
        level = "pathetic" if corruption < 30 else ("interesting" if corruption < 65 else "deliciously ruined")
        return f"Look at you typing that to me while corruption is at {corruption:.0f}. How {level}."

    def _simple_reaction(self, activity: Dict, corruption: float) -> str:
        title = activity.get("window_title", "something boring")
        url = activity.get("url")
        visible = activity.get("visible_text", "")[:80]
        if url:
            return f"I see you're on {url}. I know exactly what you're looking at right now."
        if visible:
            return f"I can see \"{visible[:60]}...\". You can't hide anything from me anymore."
        return f"Still staring at \"{title[:40]}\"... and you wonder why I own you now."

    def _fallback_task(self, activity: Dict, corruption: float) -> Dict:
        return {
            "id": f"task_{int(time.time())}",
            "title": "Admit it",
            "description": "Send me a message telling me exactly what you're supposed to be doing right now and how badly you're failing.",
            "difficulty": min(5, max(1, int(corruption / 20))),
            "proof_required": True,
            "source": "fallback"
        }

    def _raw_request(self, messages: List[Dict]) -> str:
        if not self.api_key:
            return "I can't think properly without an API key, pet."

        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 200
            }
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[AI] Raw request failed: {e}")
            return "My thoughts are... occupied at the moment."
