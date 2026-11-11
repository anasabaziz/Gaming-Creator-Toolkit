# Grok and Grok Bot

The target here is [grok.com](https://grok.com/), including Grok Bot when computer execution is needed. This is not an assumption about a separate command-line product.

Grok documents creating custom skills through conversation or uploaded material. Grok Bot documents a skill library and a computer environment. These capabilities do **not** establish automatic discovery of this GitHub folder, installation of video dependencies, or guaranteed resource limits for large recordings.

## Setup

1. Make the complete public toolkit available to the intended Grok environment using its supported file/repository workflow. Give it `README.md`, `AGENTS.md` and `setup/onboarding.md`. Do not upload private profiles/media merely to install the toolkit.
2. Ask Grok to read the five canonical `skills/*/SKILL.md` files and register them through its supported custom-skill workflow. Preserve the shared-file references and first-run customization requirement. Keep the entire package accessible; uploading one instruction file is insufficient for rendering.
3. Start customization. Save confirmed profiles in that workspace's private `.creator-toolkit/` directory where file access exists. If the session cannot persist/access the package, stop setup and explain the missing capability; do not claim the toolkit was installed.
4. For Grok Bot with a terminal/filesystem, run the same Python dependency checks and `scripts/doctor.py` inside its computer. Establish actual media, image-editing, playback/listening and GUI capability before production. Ordinary chat can help draft a brief, but this does not imply a completed video workflow.
5. Test skill recall and a small synthetic workflow. Record the actual result in the compatibility matrix. No automatic routine, connector, schedule or publication is part of installation.

Suggested setup request:

> Use the attached Gaming Creator Toolkit as a complete project. Read its AGENTS.md and onboarding guide. Help me register the five skills using your supported skill mechanism, keeping their shared resources accessible. Ask me for customization before production. Identify tools you cannot access; do not invent successful installation or checks.

Official references: [Grok custom skills](https://x.ai/news/grok-skills), [Grok Bot computer environment](https://docs.x.ai/grok-bot/overview), [Grok Bot skills](https://docs.x.ai/grok-bot/skills-routines-and-automations). Consult current product documentation if its UI changes. Actual import, skill recall and media execution remain release checks in [validation](../validation.md).
