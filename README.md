# Humblr

**A persistent, intelligent, teasing desktop presence that watches you.**

Humblr is a Windows-only desktop companion (dominant male character) that runs in the background, monitors your activity in real-time, reacts to what you're doing, assigns you tasks, changes your environment, and slowly "corrupts" your desktop the more you use it.

> **THIS IS ADULT FETISH SOFTWARE.**
> It contains heavy elements of humiliation, domination, submission, exposure, and erotic control.
> It will monitor your screen and typing. It will modify your desktop (wallpaper, colors, etc.).
> It is designed to be difficult to ignore.

**USE ENTIRELY AT YOUR OWN RISK.**

## Features

- Real-time monitoring: active window title, process name, typing volume / keystroke rate
- Dynamic, contextual comments and reactions based on what you're doing
- AI-powered chat with Humblr (dominant personality) using xAI / OpenAI compatible APIs
- Dynamic task generation with real submission themes (with proof requirements)
- Corruption / submission progress that grows over time and activity
- Autonomous actions: pushes messages, changes wallpaper, alters accent color, renames things
- Real system integration:
  - Wallpaper cycling (local + generated images)
  - Accent color changes
  - Icon/folder name changes (optional)
- Proof system for completed tasks
- Global killswitch: **Ctrl + Shift + K**
- Optional auto-start on login
- Persistent state (JSON)
- Modern dark CustomTkinter UI with pink/purple accents

## Strong Warnings

1. **Antivirus / Security software will likely flag this.**  
   Keylogging + system modification behavior looks exactly like malware. You may need to add exclusions.

2. **It makes permanent(ish) changes to your computer.**  
   Wallpaper, colors, file names. Have a restore plan.

3. **Privacy.**  
   It sees your active window titles and keystroke patterns. Do **not** run this on a work computer or any machine where you handle sensitive information.

4. **Consent & mental health.**  
   This is designed to be intense and psychologically immersive. Stop immediately if it stops being fun.

5. **Legal / platform rules.**  
   Features involving posting to X/Twitter or distributing images carry risk. Only use with accounts and content you fully control.

6. **Kill switch always works.**  
   Ctrl+Shift+K should terminate the process even if the UI is hidden.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Administrator rights recommended for some system changes

## Quick Start

1. Clone or download this repo into `Documents\GitHub\Humblr`
2. Run `setup.bat` (first time only)
3. Edit `config.json`
4. Run `run.bat` or `python main.py`

## Configuration (`config.json`)

See `config.json.example`.

Important keys:
- `api_key` — Your xAI or OpenAI compatible key
- `api_base` — `https://api.x.ai/v1` for xAI
- `model` — e.g. `grok-beta` or `gpt-4o`
- `enable_monitoring`, `enable_autonomous`, etc.
- `image_gen_enabled`

## Architecture

- `main.py` — Entry point, starts UI + background threads
- `humblr/` package — core logic
  - `monitor.py` — window + input monitoring
  - `ai.py` — chat and dynamic generation
  - `tasks.py` — task engine + proof
  - `corruption.py` — progression system
  - `system_actions.py` — wallpaper, colors, notifications, startup
  - `storage.py` — save/load state
  - `ui.py` — CustomTkinter interface
  - `hotkeys.py` — global killswitch

## Roadmap / Current Status

This is a from-scratch implementation. Many features are present in skeleton + core form. Advanced autonomous behavior and image generation are extensible.

## License

See LICENSE. This software is provided as-is for personal adult entertainment use only.

**Again: use responsibly. You are in control.**
