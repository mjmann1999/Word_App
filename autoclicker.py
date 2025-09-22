"""Advanced macOS autoclicker with a Tkinter interface and global hotkeys.

This application is written specifically for macOS.  It relies on Quartz APIs to
perform low-level mouse automation and requires that the script be granted
"Accessibility" permissions (System Settings ▸ Privacy & Security ▸
Accessibility).

Dependencies
------------
Install the dependencies with::

    python3 -m pip install -r requirements.txt

Running the Application
-----------------------
Launch the UI with::

    python3 autoclicker.py

"""
from __future__ import annotations

import threading
import time
import random
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import Quartz
import AppKit
from pynput import keyboard
import tkinter as tk
from tkinter import ttk, messagebox

# macOS mouse button mappings -------------------------------------------------

BUTTON_EVENT_MAP = {
    "left": (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, 0),
    "right": (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, 1),
    "middle": (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, 2),
}

CLICK_MULTIPLIER = {
    "single": 1,
    "double": 2,
    "triple": 3,
}

SPECIAL_KEY_ALIASES = {
    "cmd": "<cmd>",
    "command": "<cmd>",
    "⌘": "<cmd>",
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "⌃": "<ctrl>",
    "alt": "<alt>",
    "option": "<alt>",
    "⌥": "<alt>",
    "shift": "<shift>",
    "⇧": "<shift>",
    "enter": "<enter>",
    "return": "<enter>",
    "space": "<space>",
    "spacebar": "<space>",
    "tab": "<tab>",
    "capslock": "<caps_lock>",
    "esc": "<esc>",
    "escape": "<esc>",
    "f1": "<f1>",
    "f2": "<f2>",
    "f3": "<f3>",
    "f4": "<f4>",
    "f5": "<f5>",
    "f6": "<f6>",
    "f7": "<f7>",
    "f8": "<f8>",
    "f9": "<f9>",
    "f10": "<f10>",
    "f11": "<f11>",
    "f12": "<f12>",
}


@dataclass
class ClickSettings:
    interval: float = 0.1
    randomize: bool = False
    random_range: float = 0.0
    button: str = "left"
    click_type: str = "single"
    start_delay: float = 0.0
    run_duration: float = 0.0  # 0 for unlimited
    burst_count: int = 0  # 0 for unlimited
    hold_duration: float = 0.0
    follow_cursor: bool = True
    fixed_position: Tuple[int, int] = (0, 0)


class HotkeyError(Exception):
    """Raised when the user enters an invalid hotkey definition."""


class AutoClicker:
    def __init__(self, settings_provider: Callable[[], ClickSettings]) -> None:
        self._settings_provider = settings_provider
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._is_running = False
        self._start_callback: Optional[Callable[[], None]] = None
        self._stop_callback: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ public
    def start(self) -> None:
        with self._state_lock:
            if self._is_running:
                return
            self._is_running = True
        self._stop_event.clear()
        try:
            settings = self._settings_provider()
        except Exception:
            with self._state_lock:
                self._is_running = False
            return

        self._thread = threading.Thread(target=self._run, args=(settings,), daemon=True)
        self._thread.start()
        if self._start_callback:
            self._start_callback()

    def stop(self) -> None:
        with self._state_lock:
            if not self._is_running:
                return
            self._is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=1.0)
        if not self._thread or not self._thread.is_alive():
            self._thread = None

    def toggle(self) -> None:
        if self.is_running:
            self.stop()
        else:
            self.start()

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._is_running

    def on_start(self, callback: Callable[[], None]) -> None:
        self._start_callback = callback

    def on_stop(self, callback: Callable[[], None]) -> None:
        self._stop_callback = callback

    # ----------------------------------------------------------------- private
    def _run(self, settings: ClickSettings) -> None:
        if settings.start_delay > 0:
            time.sleep(settings.start_delay)

        start_time = time.monotonic()
        clicks_performed = 0

        while not self._stop_event.is_set():
            # Check run duration limit
            if settings.run_duration > 0:
                elapsed = time.monotonic() - start_time
                if elapsed >= settings.run_duration:
                    break

            position = self._get_target_position(settings)
            self._perform_click(position, settings)
            clicks_performed += 1

            # Check burst limit
            if settings.burst_count > 0 and clicks_performed >= settings.burst_count:
                break

            interval = settings.interval
            if settings.randomize and settings.random_range > 0:
                offset = random.uniform(-settings.random_range, settings.random_range)
                interval = max(0.005, settings.interval + offset)

            # sleep for the required time unless asked to stop
            end_time = time.monotonic() + interval
            while not self._stop_event.is_set() and time.monotonic() < end_time:
                time.sleep(0.001)

        # finished
        self._stop_event.set()
        with self._state_lock:
            self._is_running = False
        thread = self._thread
        self._thread = None
        if self._stop_callback:
            self._stop_callback()
        if thread and thread is not threading.current_thread():  # pragma: no cover - safety guard
            thread.join(timeout=0.1)

    def _perform_click(self, position: Tuple[int, int], settings: ClickSettings) -> None:
        button = settings.button
        if button not in BUTTON_EVENT_MAP:
            raise ValueError(f"Unsupported button '{button}'")

        down_event, up_event, button_code = BUTTON_EVENT_MAP[button]
        total_clicks = CLICK_MULTIPLIER.get(settings.click_type, 1)

        for click_index in range(total_clicks):
            press_event = Quartz.CGEventCreateMouseEvent(
                None, down_event, position, button_code
            )
            Quartz.CGEventSetIntegerValueField(
                press_event,
                Quartz.kCGMouseEventClickState,
                click_index + 1,
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, press_event)

            # Hold the button if requested
            hold_duration = settings.hold_duration
            if hold_duration > 0:
                hold_end = time.monotonic() + hold_duration
                while not self._stop_event.is_set() and time.monotonic() < hold_end:
                    time.sleep(0.001)

            release_event = Quartz.CGEventCreateMouseEvent(
                None, up_event, position, button_code
            )
            Quartz.CGEventSetIntegerValueField(
                release_event,
                Quartz.kCGMouseEventClickState,
                click_index + 1,
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, release_event)

            time.sleep(0.01)

    def _get_target_position(self, settings: ClickSettings) -> Tuple[int, int]:
        if settings.follow_cursor:
            mouse_location = AppKit.NSEvent.mouseLocation()
            display_height = AppKit.NSScreen.mainScreen().frame().size.height
            # Quartz coordinates have the origin at the bottom-left corner
            return (int(mouse_location.x), int(display_height - mouse_location.y))

        # For fixed positions we optionally warp the cursor.
        Quartz.CGWarpMouseCursorPosition(settings.fixed_position)
        return settings.fixed_position


class HotkeyManager:
    def __init__(self, start_action: Callable[[], None], stop_action: Callable[[], None], toggle_action: Callable[[], None]):
        self.start_action = start_action
        self.stop_action = stop_action
        self.toggle_action = toggle_action
        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self.current_bindings = {
            "<cmd>+<alt>+s": self.start_action,
            "<cmd>+<alt>+x": self.stop_action,
            "<cmd>+<alt>+z": self.toggle_action,
        }
        self._restart_listener()

    def update(self, start_combo: str, stop_combo: str, toggle_combo: str) -> None:
        bindings = {}
        for combo, action in (
            (start_combo, self.start_action),
            (stop_combo, self.stop_action),
            (toggle_combo, self.toggle_action),
        ):
            formatted = self._format_combo(combo)
            bindings[formatted] = action
        self.current_bindings = bindings
        self._restart_listener()

    def shutdown(self) -> None:
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _restart_listener(self) -> None:
        if self.listener:
            self.listener.stop()
        self.listener = keyboard.GlobalHotKeys(self.current_bindings)
        self.listener.start()

    def _format_combo(self, combo: str) -> str:
        parts = [part.strip().lower() for part in combo.replace("-", "+").split("+") if part.strip()]
        if not parts:
            raise HotkeyError("Hotkey cannot be empty")

        parsed_parts = []
        for part in parts:
            if part in SPECIAL_KEY_ALIASES:
                parsed_parts.append(SPECIAL_KEY_ALIASES[part])
            elif len(part) == 1:
                parsed_parts.append(part)
            else:
                parsed_parts.append(f"<{part}>")
        formatted = "+".join(parsed_parts)

        # Quick validation: attempt to build a GlobalHotKeys instance
        try:
            keyboard.GlobalHotKeys({formatted: lambda: None})
        except Exception as exc:  # pragma: no cover - validation only
            raise HotkeyError(f"Invalid hotkey '{combo}': {exc}") from exc
        return formatted


class AutoClickerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("macOS Advanced AutoClicker")
        self.resizable(False, False)
        self.style = ttk.Style(self)
        self.style.configure("TLabel", padding=2)
        self.style.configure("TButton", padding=4)
        self.style.configure("TCheckbutton", padding=2)

        self._status_var = tk.StringVar(value="Idle")
        self._hotkey_start = tk.StringVar(value="cmd+alt+s")
        self._hotkey_stop = tk.StringVar(value="cmd+alt+x")
        self._hotkey_toggle = tk.StringVar(value="cmd+alt+z")

        self.settings = ClickSettings()
        self.autoclicker = AutoClicker(self._collect_settings)
        self.autoclicker.on_start(self._on_autoclicker_start)
        self.autoclicker.on_stop(self._on_autoclicker_stop)
        self.hotkeys = HotkeyManager(
            lambda: self.after(0, self.autoclicker.start),
            lambda: self.after(0, self.autoclicker.stop),
            lambda: self.after(0, self.autoclicker.toggle),
        )

        self._build_interface()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------- UI setup
    def _build_interface(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.grid(row=0, column=0, sticky="nsew")

        # Interval settings
        interval_frame = ttk.LabelFrame(main, text="Timing", padding=8)
        interval_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        ttk.Label(interval_frame, text="Interval (s)").grid(row=0, column=0, sticky="w")
        self.interval_entry = ttk.Entry(interval_frame)
        self.interval_entry.insert(0, str(self.settings.interval))
        self.interval_entry.grid(row=0, column=1, sticky="ew", padx=4)

        self.randomize_var = tk.BooleanVar(value=self.settings.randomize)
        randomize_check = ttk.Checkbutton(
            interval_frame,
            text="Randomize",
            variable=self.randomize_var,
            command=self._toggle_randomization,
        )
        randomize_check.grid(row=1, column=0, sticky="w")

        ttk.Label(interval_frame, text="Random range (s)").grid(row=1, column=1, sticky="w")
        self.random_range_entry = ttk.Entry(interval_frame)
        self.random_range_entry.insert(0, str(self.settings.random_range))
        self.random_range_entry.grid(row=1, column=2, sticky="ew", padx=4)
        if not self.randomize_var.get():
            self.random_range_entry.state(["disabled"])

        ttk.Label(interval_frame, text="Start delay (s)").grid(row=2, column=0, sticky="w")
        self.delay_entry = ttk.Entry(interval_frame)
        self.delay_entry.insert(0, str(self.settings.start_delay))
        self.delay_entry.grid(row=2, column=1, sticky="ew", padx=4)

        ttk.Label(interval_frame, text="Run duration (s, 0 = unlimited)").grid(row=3, column=0, sticky="w")
        self.duration_entry = ttk.Entry(interval_frame)
        self.duration_entry.insert(0, str(self.settings.run_duration))
        self.duration_entry.grid(row=3, column=1, sticky="ew", padx=4)

        ttk.Label(interval_frame, text="Burst count (0 = unlimited)").grid(row=4, column=0, sticky="w")
        self.burst_entry = ttk.Entry(interval_frame)
        self.burst_entry.insert(0, str(self.settings.burst_count))
        self.burst_entry.grid(row=4, column=1, sticky="ew", padx=4)

        ttk.Label(interval_frame, text="Hold duration (s)").grid(row=5, column=0, sticky="w")
        self.hold_entry = ttk.Entry(interval_frame)
        self.hold_entry.insert(0, str(self.settings.hold_duration))
        self.hold_entry.grid(row=5, column=1, sticky="ew", padx=4)

        for i in range(3):
            interval_frame.columnconfigure(i, weight=1)

        # Click options
        click_frame = ttk.LabelFrame(main, text="Click Options", padding=8)
        click_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)

        ttk.Label(click_frame, text="Button").grid(row=0, column=0, sticky="w")
        self.button_var = tk.StringVar(value=self.settings.button)
        button_menu = ttk.OptionMenu(click_frame, self.button_var, self.settings.button, "left", "right", "middle")
        button_menu.grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(click_frame, text="Click type").grid(row=1, column=0, sticky="w")
        self.click_type_var = tk.StringVar(value=self.settings.click_type)
        click_type_menu = ttk.OptionMenu(click_frame, self.click_type_var, self.settings.click_type, "single", "double", "triple")
        click_type_menu.grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(click_frame, text="Target mode").grid(row=2, column=0, sticky="w")
        self.follow_var = tk.BooleanVar(value=self.settings.follow_cursor)
        ttk.Radiobutton(click_frame, text="Follow cursor", variable=self.follow_var, value=True).grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(click_frame, text="Fixed position", variable=self.follow_var, value=False, command=self._toggle_fixed_position).grid(row=3, column=1, sticky="w")

        self.position_label = ttk.Label(click_frame, text=f"Fixed position: {self.settings.fixed_position}")
        self.position_label.grid(row=4, column=0, columnspan=2, sticky="w")

        capture_button = ttk.Button(click_frame, text="Capture current cursor", command=self._capture_cursor)
        capture_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=2)

        # Hotkey options
        hotkey_frame = ttk.LabelFrame(main, text="Hotkeys", padding=8)
        hotkey_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)

        ttk.Label(hotkey_frame, text="Start").grid(row=0, column=0, sticky="w")
        start_entry = ttk.Entry(hotkey_frame, textvariable=self._hotkey_start)
        start_entry.grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(hotkey_frame, text="Stop").grid(row=1, column=0, sticky="w")
        stop_entry = ttk.Entry(hotkey_frame, textvariable=self._hotkey_stop)
        stop_entry.grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(hotkey_frame, text="Toggle").grid(row=2, column=0, sticky="w")
        toggle_entry = ttk.Entry(hotkey_frame, textvariable=self._hotkey_toggle)
        toggle_entry.grid(row=2, column=1, sticky="ew", padx=4)

        ttk.Button(hotkey_frame, text="Apply Hotkeys", command=self._apply_hotkeys).grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)

        # Controls and status
        control_frame = ttk.Frame(main, padding=4)
        control_frame.grid(row=3, column=0, sticky="ew")

        ttk.Button(control_frame, text="Start", command=self.autoclicker.start).grid(row=0, column=0, padx=2)
        ttk.Button(control_frame, text="Stop", command=self.autoclicker.stop).grid(row=0, column=1, padx=2)
        ttk.Button(control_frame, text="Toggle", command=self.autoclicker.toggle).grid(row=0, column=2, padx=2)

        ttk.Label(control_frame, textvariable=self._status_var, foreground="green").grid(row=0, column=3, padx=6)

        ttk.Label(main, text="Hotkeys use the format 'cmd+alt+s'. Ensure Accessibility permissions are granted.").grid(row=4, column=0, sticky="w", pady=(6, 0))

    # ----------------------------------------------------------- event helpers
    def _on_autoclicker_start(self) -> None:
        self.after(0, lambda: self._status_var.set("Running"))

    def _on_autoclicker_stop(self) -> None:
        self.after(0, lambda: self._status_var.set("Idle"))

    def _on_close(self) -> None:
        self.autoclicker.stop()
        self.hotkeys.shutdown()
        self.destroy()

    def _toggle_randomization(self) -> None:
        if self.randomize_var.get():
            self.random_range_entry.state(["!disabled"])
        else:
            self.random_range_entry.state(["disabled"])

    def _toggle_fixed_position(self) -> None:
        if not self.follow_var.get():
            self._capture_cursor()

    def _capture_cursor(self) -> None:
        mouse_location = AppKit.NSEvent.mouseLocation()
        display_height = AppKit.NSScreen.mainScreen().frame().size.height
        position = (int(mouse_location.x), int(display_height - mouse_location.y))
        self.position_label.config(text=f"Fixed position: {position}")
        self.settings.fixed_position = position

    def _apply_hotkeys(self) -> None:
        try:
            self.hotkeys.update(
                self._hotkey_start.get(),
                self._hotkey_stop.get(),
                self._hotkey_toggle.get(),
            )
            messagebox.showinfo("Hotkeys", "Hotkeys updated successfully.")
        except HotkeyError as exc:
            messagebox.showerror("Hotkey error", str(exc))

    def _collect_settings(self) -> ClickSettings:
        try:
            interval = float(self.interval_entry.get())
            random_range = float(self.random_range_entry.get() or 0)
            start_delay = float(self.delay_entry.get() or 0)
            run_duration = float(self.duration_entry.get() or 0)
            burst_count = int(float(self.burst_entry.get() or 0))
            hold_duration = float(self.hold_entry.get() or 0)
        except ValueError as exc:
            messagebox.showerror("Invalid input", f"Please correct numeric fields: {exc}")
            raise

        settings = ClickSettings(
            interval=max(0.001, interval),
            randomize=self.randomize_var.get(),
            random_range=max(0.0, random_range),
            button=self.button_var.get(),
            click_type=self.click_type_var.get(),
            start_delay=max(0.0, start_delay),
            run_duration=max(0.0, run_duration),
            burst_count=max(0, burst_count),
            hold_duration=max(0.0, hold_duration),
            follow_cursor=self.follow_var.get(),
            fixed_position=self.settings.fixed_position,
        )
        self.settings = settings
        return settings


def main() -> None:
    app = AutoClickerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
