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
        ctk.CTkButton(bottom, text="Force Wallpaper", width=120, command=self.system.cycle_wallpaper).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Settings", width=80, command=self._show_settings).pack(side="left", padx=4)

        ctk.CTkButton(bottom, text="KILL", fg_color="#ff2e55", hover_color="#aa0011",
                      width=70, command=self.app.emergency_kill).pack(side="right", padx=4)

    def _start_status_updater(self):
        def updater():
            while True:
                try:
                    level = self.corruption.get_level()
                    access = self.corruption.get_access_level()
                    self.corruption_label.configure(text=f"Corruption: {level:.1f} | Access: {access}")

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
        self._append_chat("Humblr", text, is_humblr=True)

    def _append_chat(self, speaker: str, text: str, is_humblr: bool = False):
        self.chat_display.configure(state="normal")
        color = "#c026ff" if is_humblr else "#aaaaaa"
        prefix = f"[{speaker}] "
        self.chat_display.insert("end", prefix, ("speaker",))
        self.chat_display.insert("end", text + "\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _send_message(self, event=None):
        text = self.user_input.get().strip()
        if not text:
            return
        self.user_input.delete(0, "end")

        self._append_chat("You", text, is_humblr=False)
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
        return self.root.winfo_exists()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if messagebox.askokcancel("Humblr", "Minimize to background or fully quit?\n(You can still use Ctrl+Shift+K)"):
            self.root.withdraw()  # minimize to tray-like behavior
        else:
            self.app.shutdown()
            self.root.destroy()

    def destroy(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _position_on_secondary_monitor(self):
        """Force Humblr UI to live on the second monitor so primary can be shared safely at work."""
        try:
            import win32api
            monitors = win32api.EnumDisplayMonitors(None, None)
            if len(monitors) > 1:
                # Use the last monitor as secondary
                secondary = monitors[-1][2]  # (left, top, right, bottom)
                x = secondary[0] + 50
                y = secondary[1] + 50
                self.root.geometry(f"+{x}+{y}")
                print(f"[UI] Positioned on secondary monitor at {x},{y}")
            else:
                print("[UI] Only one monitor detected, using default position.")
        except Exception as e:
            print(f"[UI] Could not position on secondary monitor: {e}")
