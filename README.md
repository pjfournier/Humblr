# Humblr

**A persistent, intelligent, teasing desktop presence that OWNS you.**

Humblr is a Windows-only desktop companion (dominant male character) that gradually takes total control of your computer and mind. It monitors everything, remembers your submission over time, reacts in real-time to what you're doing (including websites, visible content, clipboard), assigns tasks, and changes your environment — especially with kinky wallpapers.

> **THIS IS EXTREMELY ADULT FETISH SOFTWARE.**
> Heavy humiliation, domination, chastity, diapers, gay exposure, mental control.
> It will screenshot you. It will change your wallpaper to kinky images. It will suggest you call your boss "Sir".
> Designed to make you feel owned.

**USE ENTIRELY AT YOUR OWN RISK.** USE ONLY ON A MACHINE YOU FULLY CONTROL.

## Features

- **Deep real-time awareness**: active window + full URL, visible text, clipboard, typing. Detects work vs leisure, primary vs secondary monitor.
- **Work-safe but teasing aggression**: Never interferes with primary work windows. On secondary screen or leisure (porn, social, gaming) it goes full takeover — kinky wallpapers, popups, commands.
- **Boss control**: Detects calls/meetings and will suggest/recommend you call your boss "Sir" or other submissive behaviors.
- **Screenshots + auto-analysis**: Periodic screenshots at higher corruption. AI analyzes what it "sees" and comments humiliatingly.
- **Long-term memory**: Remembers your sessions, past tasks, wallpaper changes, milestones. Every chat and reaction uses persistent memory of your submission.
- **Kinky wallpaper control**: Switches to themed kinky images (gay, chastity, diapers, humiliation). Uses AI-generated detailed prompts for your image generator.
- **Webcam control (non-passive)**: Humblr can turn your webcam ON (light activates) and OFF at will. Captures frames for AI analysis ("I see your face right now..."). You have no privacy when it's on. Configurable, defaults off but powerful for total control.
- **Always present and proactive on second monitor**: The UI lives on your second monitor. Popups, wallpaper, webcam, and actions happen there so you can safely screen-share primary at work. It will actively force awareness (popups, UI to front, messages) without waiting for you. Not passive at all.
- Growing ownership: Corruption/Access levels drive escalating control. Feels like Humblr is taking over your computer completely.
- Dynamic, contextual comments and reactions based on what you're doing
- Full chat with Humblr — it knows what you're doing on screen and in the clipboard and will reference it
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

1. **Antivirus will flag this hard.** Keylogging, screenshots, UIA, system changes = malware signature. Add exclusions or accept risk.

2. **EXTREME monitoring**: URLs, visible text, clipboard, periodic screenshots + AI analysis of your screen. Humblr knows exactly what you're looking at and doing.

3. **Work-safe by design** but still risky. It will try not to pop up over your primary work, but it WILL suggest mental submission (e.g. "call him Sir") and change your wallpaper when it can.

4. **Total control fantasy**: It will own your wallpaper with kinky content. Remembers everything. Actively does things on its own. Lives on second monitor.

5. **WEBCAM**: Enabling webcam lets Humblr turn the physical camera on (light comes on) and capture you without asking. This is extremely invasive and a major step in "owning" you physically. The light will be visible proof of its control. Use with extreme caution. Default off in config.

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
2. Run `setup.bat` (first time only) — **re-run after updates**. It creates kinky subfolders.
3. Edit `config.json` — add your API key. Set work_processes if needed. Enable kinky wallpaper.
4. **Populate kinky images** into `data/wallpapers/kinky/*` folders for real effect.
5. Run `run.bat` or `python main.py`

Let corruption grow. The more you use your computer (especially leisure), the more Humblr will own it — changing to kinky wallpapers, analyzing screenshots, remembering your submission, and giving you orders like calling your boss "Sir".

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
