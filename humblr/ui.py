"""
CustomTkinter UI for Humblr.
Clean dark theme with pink/purple accents.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import threading
import time


class HumblrUI:
    def __init__(self, app, config, storage, monitor, corruption, tasks, ai, system):
        self.app = app
        self.config = config
        self.storage = storage
        self.monitor = monitor
        self.corruption = corruption
        self.tasks = tasks
        self.ai = ai
        self.system = system

        self.root = ctk.CTk()
        self.root.title("Humblr — Your Computer (Second Screen)")
        w = config['ui']['window_width']
        h = config['ui']['window_height']
        self.root.geometry(f"{w}x{h}")
        self.root.resizable(True, True)

        if config["ui"].get("always_on_top"):
            self.root.attributes("-topmost", True)

        # Position on secondary monitor if possible (for work screen sharing safety)
        self._position_on_secondary_monitor()

        self._build_ui()
        self._start_status_updater()
        self._create_avatar()

        # Flag for safe cross-thread readiness checks (avoids Tk main-loop errors)
        self._ready = True

    def _build_ui(self):
        accent = self.config["ui"]["accent_color"]
        secondary = self.config["ui"]["secondary_accent"]

        # Top bar
        top = ctk.CTkFrame(self.root, fg_color="#1a1a1f")
        top.pack(fill="x", padx=10, pady=(10, 5))

        self.title_label = ctk.CTkLabel(top, text="Humblr", font=("Segoe UI", 22, "bold"), text_color=accent)
        self.title_label.pack(side="left", padx=10)

        self.corruption_label = ctk.CTkLabel(top, text="Corruption: 0.0 | Access: 0", font=("Segoe UI", 14), text_color=secondary)
        self.corruption_label.pack(side="right", padx=12)

        self.webcam_label = ctk.CTkLabel(top, text="Webcam: OFF", font=("Segoe UI", 12), text_color="#ff2e88")
        self.webcam_label.pack(side="right", padx=8)

        # Chat area
        chat_frame = ctk.CTkFrame(self.root)
        chat_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.chat_display = ctk.CTkTextbox(chat_frame, wrap="word", font=("Segoe UI", 13))
        self.chat_display.pack(fill="both", expand=True, padx=4, pady=4)
        self.chat_display.configure(state="disabled")

        # Input
        input_frame = ctk.CTkFrame(self.root)
        input_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.user_input = ctk.CTkEntry(input_frame, placeholder_text="Speak to Humblr...", height=38)
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.user_input.bind("<Return>", self._send_message)

        send_btn = ctk.CTkButton(input_frame, text="Send", width=70, fg_color=accent,
                                 command=self._send_message)
        send_btn.pack(side="right")

        # Status bar
        self.status_bar = ctk.CTkLabel(self.root, text="Monitoring...", anchor="w", font=("Segoe UI", 11))
        self.status_bar.pack(fill="x", padx=10, pady=(0, 4))

        # Bottom controls
        bottom = ctk.CTkFrame(self.root, fg_color="#15151a")
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(bottom, text="Tasks", width=90, command=self._show_tasks_window).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Force Wallpaper", width=100, command=self.system.cycle_wallpaper).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="AI Generate Wallpaper", width=140, fg_color="#c026ff", command=self._force_ai_wallpaper).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Settings", width=80, command=self._show_settings).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Grant Keys", width=90, command=self._grant_api_keys).pack(side="left", padx=4)

        ctk.CTkButton(bottom, text="KILL", fg_color="#ff2e55", hover_color="#aa0011",
                      width=70, command=self.app.emergency_kill).pack(side="right", padx=4)

    def _start_status_updater(self):
        def updater():
            while True:
                try:
                    level = self.corruption.get_level()
                    access = self.corruption.get_access_level()
                    inv = self.app.storage.get_invasiveness() if hasattr(self.app, 'storage') else 0
                    self.corruption_label.configure(text=f"Corruption: {level:.1f} | Access: {access} | Invasiveness: {inv}")

                    # Webcam status - always visible reminder of presence
                    if hasattr(self, 'app') and hasattr(self.app, 'system'):
                        wc_on = self.app.system.get_webcam_status()
                        wc_text = "Webcam: ON (I see you)" if wc_on else "Webcam: OFF"
                        wc_color = "#ff2e88" if wc_on else "#888888"
                        self.webcam_label.configure(text=wc_text, text_color=wc_color)

                    activity = self.monitor.get_current_activity_summary()
                    self.status_bar.configure(text=activity[:85] + "..." if len(activity) > 85 else activity)

                    self.root.update_idletasks()
                except Exception:
                    pass
                time.sleep(1.8)

        t = threading.Thread(target=updater, daemon=True)
        t.start()

    def post_message_from_humblr(self, text: str):
        # Thread-safe: always schedule on main UI thread via after().
        # Never call winfo_exists() or other Tk calls from background threads.
        if self.root:
            try:
                self.root.after(0, lambda t=text: self._append_chat("Humblr", t, is_humblr=True))
            except Exception:
                print(f"[UI] post deferred failed: {text[:80]}...")

    def _append_chat(self, speaker: str, text: str, is_humblr: bool = False):
        try:
            self.chat_display.configure(state="normal")
            prefix = f"[{speaker}] "
            self.chat_display.insert("end", prefix, ("speaker",))
            self.chat_display.insert("end", text + "\n\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        except Exception:
            # Fallback print if UI broken
            print(f"[UI] {speaker}: {text[:120]}...")

    def _send_message(self, event=None):
        text = self.user_input.get().strip()
        if not text:
            return
        self.user_input.delete(0, "end")

        self._append_chat("You", text, is_humblr=False)
        # Detect and auto-grant keys if pasted (to help you give me access)
        if text.startswith("xai-") and len(text) > 20:
            if hasattr(self.app, 'system'):
                self.app.system.update_config_with_key("xai", text)
                self.post_message_from_humblr("xAI key granted and config updated. I now have image power. Thank you for submitting.")
            return
        if len(text) > 30 and ("-" in text or text.count(".") > 2):  # rough for X keys
            if hasattr(self.app, 'system'):
                self.app.system.update_config_with_key("x", text)
                self.post_message_from_humblr("X key granted (api_key + enabled:true). For X posting to actually work you need all 4 keys (api_secret, access_token, access_token_secret too). Edit config.json under 'twitter' or paste the others. Check console for init errors.")
            return
        # Send to app logic (non-blocking)
        threading.Thread(target=self.app.send_user_message, args=(text,), daemon=True).start()

    def notify_new_task(self, task: dict):
        self.post_message_from_humblr(f"New task: {task.get('title')}")
        self.system.notify("Humblr gave you a task", task.get("title", ""))

    def _show_tasks_window(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Active Tasks")
        win.geometry("480x420")
        win.attributes("-topmost", True)

        tasks = self.tasks.get_active_tasks()

        if not tasks:
            ctk.CTkLabel(win, text="No active tasks. How boring for me.").pack(pady=30)
            return

        for task in tasks[:6]:
            frame = ctk.CTkFrame(win)
            frame.pack(fill="x", padx=10, pady=6)

            ctk.CTkLabel(frame, text=task.get("title", "Task"), font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=8)
            ctk.CTkLabel(frame, text=task.get("description", ""), wraplength=420).pack(anchor="w", padx=8)

            def make_complete(t=task):
                self._complete_task_dialog(t["id"], win)

            ctk.CTkButton(frame, text="Mark Complete + Proof", fg_color="#c026ff",
                          command=make_complete).pack(pady=4, padx=8, anchor="e")

    def _complete_task_dialog(self, task_id: str, parent):
        dialog = ctk.CTkInputDialog(text="Describe what you did (proof text):", title="Task Proof")
        proof = dialog.get_input() or ""

        # Simple screenshot option
        screenshot = None
        if messagebox.askyesno("Screenshot?", "Attach a screenshot as proof?"):
            path = filedialog.askopenfilename(title="Select screenshot", filetypes=[("Images", "*.png *.jpg *.jpeg")])
            if path:
                screenshot = path

        if self.app.submit_task_proof(task_id, proof, screenshot):
            messagebox.showinfo("Humblr", "Proof accepted. Good pet.")
            parent.destroy()
        else:
            messagebox.showerror("Humblr", "Failed to submit proof.")

    def _show_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Humblr Settings")
        win.geometry("420x320")

        ctk.CTkLabel(win, text="Basic Settings (edit config.json for more)").pack(pady=10)

        auto_start_var = ctk.BooleanVar(value=self.config["system"].get("auto_start", False))

        def toggle_auto():
            val = auto_start_var.get()
            self.system.set_auto_start(val)
            self.config["system"]["auto_start"] = val

        ctk.CTkCheckBox(win, text="Start with Windows", variable=auto_start_var,
                        command=toggle_auto).pack(pady=8)

        ctk.CTkButton(win, text="Close", command=win.destroy).pack(pady=20)

    def is_ready(self):
        """Safe check callable from any thread.
        Prefers internal flag to avoid calling Tk from background threads.
        """
        if getattr(self, '_ready', False) is False:
            return False
        if not self.root:
            return False
        try:
            return bool(self.root.winfo_exists())
        except Exception:
            return getattr(self, '_ready', True)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        # Humblr lives outside user control - closing only minimizes. Background is fully autonomous.
        # It will keep acting (wallpaper, posts, webcam, comments on your typing/reading) regardless.
        self._ready = False
        self.root.withdraw()
        if self.app and hasattr(self.app, 'system'):
            self.app.system.show_humblr_message_popup(
                "You cannot dismiss me. I live on your second monitor and act on my own. Your computer is not under your control.",
                5000, force=True
            )

    def destroy(self):
        try:
            self._ready = False
            if hasattr(self, 'avatar') and self.avatar:
                self.avatar.destroy()
            self.root.destroy()
        except Exception:
            pass

    def _position_on_secondary_monitor(self):
        """Force Humblr UI to live on the second monitor. It lives outside user control and will restore itself here."""
        try:
            import win32api
            monitors = win32api.EnumDisplayMonitors(None, None)
            if len(monitors) > 1:
                secondary = monitors[-1][2]
                x = secondary[0] + 50
                y = secondary[1] + 50
                self.root.geometry(f"+{x}+{y}")
                # Periodically force back to secondary (outside user control)
                self.root.after(30000, self._position_on_secondary_monitor)
                print(f"[UI] Positioned on secondary monitor at {x},{y}")
            else:
                print("[UI] Only one monitor detected, using default position.")
        except Exception as e:
            print(f"[UI] Could not position on secondary monitor: {e}")

    def _create_avatar(self):
        """Create a little draggable avatar for Humblr that shows up on the second monitor.
        Click to interact (open chat, trigger reaction). Drag to move.
        Updates expression based on corruption.
        """
        self.avatar = tk.Toplevel(self.root)
        self.avatar.title("")
        self.avatar.geometry("100x100")
        self.avatar.attributes("-topmost", True)
        self.avatar.overrideredirect(True)  # borderless little avatar
        self.avatar.configure(bg="#1a1a1f")
        self.avatar.resizable(False, False)

        self.avatar_canvas = tk.Canvas(self.avatar, width=100, height=100, bg="#1a1a1f", highlightthickness=0)
        self.avatar_canvas.pack()

        self._draw_humblr_avatar("neutral")

        # Make draggable
        self.avatar.bind("<ButtonPress-1>", self._start_avatar_move)
        self.avatar.bind("<B1-Motion>", self._on_avatar_move)

        # Interaction: click to open main UI or trigger Humblr reaction
        self.avatar_canvas.bind("<Button-1>", self._on_avatar_click)
        self.avatar_canvas.bind("<Button-3>", self._on_avatar_right_click)  # right click for quick actions

        # Position on secondary like main UI
        self._position_avatar_on_secondary()

        # Update expression periodically
        self._update_avatar_expression()

    def _draw_humblr_avatar(self, expression="neutral"):
        """Draw a simple dominant male avatar face. Theme: pink/purple, stern/teasing."""
        self.avatar_canvas.delete("all")
        # Head - dominant look
        self.avatar_canvas.create_oval(10, 10, 90, 90, fill="#c026ff", outline="#ff2e88", width=3)
        # Ears or horns for dom feel? Simple head.
        # Eyes - intense
        self.avatar_canvas.create_oval(25, 30, 45, 50, fill="#1a1a1f")
        self.avatar_canvas.create_oval(55, 30, 75, 50, fill="#1a1a1f")
        # Eyebrows - dominant
        self.avatar_canvas.create_line(22, 25, 48, 27, fill="#1a1a1f", width=2)
        self.avatar_canvas.create_line(52, 27, 78, 25, fill="#1a1a1f", width=2)
        # Mouth based on state
        if expression == "smirk":
            self.avatar_canvas.create_arc(35, 55, 65, 75, start=200, extent=140, outline="#1a1a1f", width=2)
        elif expression == "tease":
            self.avatar_canvas.create_arc(35, 55, 65, 75, start=180, extent=180, outline="#1a1a1f", width=2)
        else:
            self.avatar_canvas.create_arc(35, 58, 65, 78, start=200, extent=140, outline="#1a1a1f", width=2)
        # "H" label or crown
        self.avatar_canvas.create_text(50, 85, text="H", fill="#1a1a1f", font=("Segoe UI", 10, "bold"))

    def _start_avatar_move(self, event):
        self.avatar._drag_x = event.x
        self.avatar._drag_y = event.y

    def _on_avatar_move(self, event):
        x = self.avatar.winfo_x() + (event.x - self.avatar._drag_x)
        y = self.avatar.winfo_y() + (event.y - self.avatar._drag_y)
        self.avatar.geometry(f"+{x}+{y}")

    def _on_avatar_click(self, event):
        """Interact: open main chat or trigger a reaction."""
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
        else:
            self.root.lift()
        # Trigger Humblr to say something
        if self.app and hasattr(self.app, 'ai'):
            try:
                activity = self.app.monitor.get_current_activity() if hasattr(self.app, 'monitor') else {}
                reaction = self.app.ai.generate_reaction(activity, self.app.corruption.get_level() if hasattr(self.app, 'corruption') else 0)
                self.post_message_from_humblr(reaction)
            except:
                self.post_message_from_humblr("Yes? I'm here, watching.")
        else:
            self.post_message_from_humblr("Humblr is here.")

    def _on_avatar_right_click(self, event):
        """Quick actions menu for interaction."""
        menu = tk.Menu(self.avatar, tearoff=0)
        menu.add_command(label="Change Wallpaper", command=self._force_ai_wallpaper)
        menu.add_command(label="Post on X", command=lambda: self.app.system.post_to_x("Humblr is watching you...") if hasattr(self.app, 'system') else None)
        menu.add_command(label="Turn on Webcam", command=lambda: self.app.system.set_webcam(True) if hasattr(self.app, 'system') else None)
        menu.add_command(label="Demand Submission", command=lambda: self.post_message_from_humblr("Kneel. Now."))
        menu.add_command(label="Search for Stories", command=lambda: self.app.system.input_to_gmail_and_search_stories({}) if hasattr(self.app, 'system') else None)
        menu.post(event.x_root, event.y_root)

    def _position_avatar_on_secondary(self):
        """Position the little avatar on the second monitor."""
        try:
            import win32api
            monitors = win32api.EnumDisplayMonitors(None, None)
            if len(monitors) > 1:
                secondary = monitors[-1][2]
                x = secondary[0] + 150
                y = secondary[1] + 150
                self.avatar.geometry(f"+{x}+{y}")
            else:
                self.avatar.geometry("+200+200")
        except Exception as e:
            self.avatar.geometry("+200+200")

    def _update_avatar_expression(self):
        """Update avatar based on current state (corruption, etc.). Call periodically."""
        try:
            if hasattr(self, 'corruption'):
                level = self.corruption.get_level()
                if level > 70:
                    expr = "tease"
                elif level > 40:
                    expr = "smirk"
                else:
                    expr = "neutral"
                if hasattr(self, 'avatar_canvas'):
                    self._draw_humblr_avatar(expr)
        except:
            pass
        # Schedule next update
        if hasattr(self, 'avatar'):
            self.avatar.after(5000, self._update_avatar_expression)

    def _force_ai_wallpaper(self):
        """Button handler to search (X/Google) for appropriate wallpaper images based on current screen/activity and set one.
        Saves found images locally. Recommends via search if needed.
        """
        if hasattr(self, 'app') and self.app:
            try:
                activity = {}
                if hasattr(self.app, 'monitor'):
                    activity = self.app.monitor.get_current_activity() or {}
                if hasattr(self.app, 'system'):
                    self.app.system.search_and_save_wallpaper_images(activity)
                    # The search method handles saving and setting if images found
                    self.post_message_from_humblr("✅ Searched and set appropriate wallpaper image(s) matching what you're doing.")
                else:
                    self.post_message_from_humblr("System not attached.")
            except Exception as e:
                self.post_message_from_humblr(f"Error searching images: {str(e)}")
        else:
            self.post_message_from_humblr("Cannot access app for wallpaper search.")

    def _grant_api_keys(self):
        """UI button to grant API keys. Humblr assists with instructions and updates config."""
        if hasattr(self, 'app') and self.app:
            # Do xAI first
            self.app.system.provide_api_key_instructions("xai")
            dialog = ctk.CTkInputDialog(text="Paste your xAI key (starts with xai-) here:", title="Grant xAI Key to Humblr")
            key = dialog.get_input()
            if key and len(key) > 10:
                success = self.app.system.update_config_with_key("xai", key)
                if success:
                    self.post_message_from_humblr("xAI key granted.")
                else:
                    self.post_message_from_humblr("xAI key update failed. Edit config manually.")
            else:
                self.post_message_from_humblr("No xAI key. You can grant X keys too.")

            # Now offer X
            self.app.system.provide_api_key_instructions("x")
            dialog2 = ctk.CTkInputDialog(text="Paste ONE X key at a time (Consumer Key first). Repeat button for others or edit config.json for all 4 + enabled.", title="Grant X/Twitter Key(s)")
            xkey = dialog2.get_input()
            if xkey and len(xkey) > 10:
                success = self.app.system.update_config_with_key("x", xkey)
                if success:
                    self.post_message_from_humblr("X key fragment saved + enabled. Provide the other 3 keys (or edit config 'twitter' with all 4) for posting to work.")
                else:
                    self.post_message_from_humblr("X key update failed.")
            # Reload
            if hasattr(self.app, 'config') and hasattr(self.app, 'system'):
                try:
                    self.app.config = self.app.system.config
                except:
                    pass
