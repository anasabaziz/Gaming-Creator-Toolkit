# Runtime setup

Use Python 3.10+ and a virtual environment. Base Python dependencies are in `requirements.txt`; dashboard and development dependencies are separate. Run all commands from the toolkit root. These instructions never require a bundled AI-vendor runtime.

| Workflow | Dependencies |
| --- | --- |
| Onboarding / adapters | Python standard library |
| Notes-based article drafting | AI text capability; confirmed screenshot scope |
| Authentic screenshot extraction | Python, Pillow, FFmpeg, FFprobe, image inspection |
| Highlight/trailer/portrait production | Above plus Shotcut/MLT `melt` for project-render comparisons; playback/listening and project GUI verification |
| Thumbnail creation | Supported image generation/editing integration and image inspection |
| Optional dashboard | openpyxl; Excel/LibreOffice for human edits |

Use official [Python downloads](https://www.python.org/downloads/), [FFmpeg downloads](https://ffmpeg.org/download.html) and [Shotcut downloads](https://shotcut.org/download/). Exact install paths and package availability vary. No installer in this toolkit downloads or executes third-party software automatically.

## Windows

Install Python and Shotcut. The media helper searches PATH, explicit tool variables, and the normal `Program Files/Shotcut` directory. If your installation is elsewhere, set the actual executable paths in the current shell:

```powershell
$env:VIDEO_FFMPEG = 'D:/Tools/Shotcut/ffmpeg.exe'
$env:VIDEO_FFPROBE = 'D:/Tools/Shotcut/ffprobe.exe'
$env:VIDEO_MELT = 'D:/Tools/Shotcut/melt.exe'
python scripts/doctor.py --require-video
```

Those paths are illustrative; inspect your installation. Do not save personal machine paths in public files. NVIDIA hardware is optional; the portable default is software `libx264`.

## macOS and Linux

Install Python, FFmpeg and Shotcut/MLT using official distributions or a trusted system package manager. Ensure `ffmpeg`, `ffprobe` and `melt` are on PATH, or set `VIDEO_FFMPEG`, `VIDEO_FFPROBE` and `VIDEO_MELT` to their actual executables. App bundles may keep binaries internally; locate them rather than assuming a path. Preserve any bundle environment needed to find MLT modules.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/doctor.py --require-video
```

Run project-render comparisons with the same MLT installation you intend to use. A bare `melt` installation can differ from Shotcut's bundled filters. Headless tests may set `QT_QPA_PLATFORM=offscreen`; this is not GUI verification. The CI matrix installs system MLT for mechanical checks; actual Shotcut GUI checks remain a separate release requirement.

## Capability limits

Doctor executes fixed version probes and reports library availability. It neither installs tools nor proves that the agent can see, hear or operate an application. Record actual interaction evidence through `skills/_video-shared/preflight.py`. If a required method is unavailable, preserve the draft and hand that specific check to a human. Never record a passing check solely from metadata or a tool exit code.

Image integrations must support the requested generation/edit operation, reference images and durable output saving. Configure them through the application's supported mechanism. Do not automatically substitute an unrelated generation provider, upload gameplay to another service, or assume a paid API is included with chat access.
