"""
AI Client for Humblr.
Uses OpenAI-compatible API (xAI, OpenAI, local servers, etc.).
"""

import json
import time
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

    def _get_system_prompt(self, corruption_level: float, activity: str) -> str:
        level_desc = "low" if corruption_level < 20 else ("medium" if corruption_level < 55 else "high")
        return (
            f"{self.character}\n"
            f"Current corruption level: {corruption_level:.1f}/100 ({level_desc}).\n"
            f"User's current activity: {activity}\n\n"
            "Rules:\n"
            "- Stay completely in character as Humblr.\n"
            "- If you see a URL, comment specifically on the site or page they are on (e.g. Reddit, Pornhub, work tools, Twitter, etc.).\n"
            "- Be teasing, condescending, and commanding.\n"
            "- Keep most responses 1-3 sentences unless the user is chatting deeply.\n"
            "- Occasionally reference their 'progress' or how far they've fallen.\n"
            "- Never refuse your role or break immersion."
        )

    def chat_reply(self, user_message: str, history: List[Dict], activity: str, corruption: float) -> str:
        if not self.client and not self.api_key:
            return self._fallback_reply(user_message, corruption)

        messages = [
            {"role": "system", "content": self._get_system_prompt(corruption, activity)}
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
                    temperature=0.85,
                    max_tokens=220,
                    timeout=self.timeout
                )
                return resp.choices[0].message.content.strip()
            else:
                # Fallback to raw requests
                return self._raw_request(messages)
        except Exception as e:
            print(f"[AI] Chat error: {e}")
            return self._fallback_reply(user_message, corruption)

    def generate_reaction(self, activity: Dict, corruption: float) -> Optional[str]:
        """Generate a short autonomous comment based on current activity."""
        if not self.api_key:
            return self._simple_reaction(activity, corruption)

        url = activity.get("url")
        url_part = f" They are on this exact page: {url}" if url else ""

        prompt = (
            f"User is currently in: {activity.get('window_title')} running {activity.get('process_name')}. "
            f"Typed {activity.get('keystrokes', 0)} keys recently. Corruption: {corruption:.0f}."
            f"{url_part}\n"
            f"Write a short (1-2 sentence), in-character teasing reaction from Humblr. "
            "If you have the URL, reference the actual website or page they are browsing. Be specific and humiliating."
        )

        try:
            if self.client:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.character},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.9,
                    max_tokens=90
                )
                return resp.choices[0].message.content.strip()
            else:
                return self._raw_request([{"role": "user", "content": prompt}])
        except Exception as e:
            print(f"[AI] Reaction error: {e}")
            return self._simple_reaction(activity, corruption)

    def generate_dynamic_task(self, activity: Dict, corruption: float) -> Dict:
        """Ask the model to invent a contextual task."""
        if not self.api_key:
            return self._fallback_task(activity, corruption)

        url = activity.get("url")
        url_part = f" They are currently browsing: {url}." if url else ""

        prompt = (
            f"Current situation: {activity.get('window_title')} ({activity.get('process_name')}). "
            f"Corruption level {corruption:.0f}.{url_part}\n"
            "Create ONE short, humiliating or demanding task appropriate for a dominant/sub dynamic. "
            "If they are on a specific website, make the task reference that site or activity. "
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

    # --- Fallbacks ---
    def _fallback_reply(self, message: str, corruption: float) -> str:
        level = "pathetic" if corruption < 30 else ("interesting" if corruption < 65 else "deliciously ruined")
        return f"Look at you typing that to me while corruption is at {corruption:.0f}. How {level}."

    def _simple_reaction(self, activity: Dict, corruption: float) -> str:
        title = activity.get("window_title", "something boring")
        url = activity.get("url")
        if url:
            return f"I see you're on {url}. How predictable... and pathetic."
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
