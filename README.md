# macOS Advanced AutoClicker

This repository contains a macOS-focused Python autoclicker with a desktop user
interface, extensive configuration options, and global hotkeys. The
application relies on Quartz (via PyObjC) for precise mouse automation and uses
`pynput` to provide customizable system-wide hotkeys.

> **Note**
> macOS requires that any automation utility be granted "Accessibility"
> permissions. You will be prompted the first time the script attempts to send
> mouse events. You can manage permissions at **System Settings ▸ Privacy &
> Security ▸ Accessibility**.

## Features

- Tkinter-based configuration UI with live status updates.
- Adjustable click interval, optional random jitter, and configurable start delay.
- Limit automation by run duration or total number of clicks (burst mode).
- Support for single, double, or triple clicks using left, right, or middle buttons.
- Fixed-position clicking (with live cursor capture) or follow-the-cursor mode.
- Optional button hold duration for press-and-hold scenarios.
- Customizable global hotkeys for start, stop, and toggle actions.

## Requirements

- Python 3.9 or newer (recommended)
- macOS 11 Big Sur or newer (tested on Apple Silicon and Intel Macs)
- Accessibility permission for the Python interpreter running the script

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

The `pyobjc-framework-Quartz` package is sizeable; installation can take a few
minutes on slower connections.

## Usage

1. Install dependencies.
2. Run the application:
   ```bash
   python3 autoclicker.py
   ```
3. Configure the desired click parameters, cursor mode, and hotkeys.
4. Press **Start** (or use your hotkey) to begin automated clicking. Use the
   **Stop** button or hotkey to halt execution.

The application minimizes CPU usage between clicks and stops automatically when
it reaches the configured burst count or run duration.

## Hotkey Format

Enter hotkeys using `+` as the separator (e.g., `cmd+alt+s`). Supported modifier
names include `cmd`, `ctrl`, `alt`, and `shift`. Function keys can be entered as
`f1` … `f12`. The UI validates hotkeys before applying them.

## Troubleshooting

- **No clicks happen** – Ensure macOS granted Accessibility permission to the
  Python executable. Re-open System Settings if necessary.
- **Hotkeys do not trigger** – Avoid duplicates that conflict with system
  shortcuts. Some combinations, especially `cmd+space`, are reserved by the OS.
- **High CPU usage** – Increase the click interval or disable extremely rapid
  burst clicks.

## License

This project is provided under the MIT License. See [`LICENSE`](LICENSE) if
included with your distribution, or adapt the script for personal use.
