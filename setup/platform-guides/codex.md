# Codex

Open the standalone toolkit repository as the project. Run:

```text
python scripts/install.py --platform codex
```

This creates `.agents/skills/<name>/SKILL.md` discovery adapters pointing to the canonical `skills/` files. Keep the whole repository together. Restart/reload the project if the new skills are not visible, then ask Codex to read `AGENTS.md` and begin onboarding. Invoke a skill by name or, where supported, `$gameplay-highlights` etc.

Project guidance comes from `AGENTS.md`; each skill also checks onboarding directly. Installation does not overwrite global settings or install vendor plugins. Use the available imagegen integration for thumbnails, following its own requirements; if absent, configure an approved integration or leave generation blocked. Required media tools are [separate](../dependencies.md).

Codex's current skill documentation describes `SKILL.md` metadata, progressive loading and `.agents/skills` project discovery: [official guide](https://learn.chatgpt.com/docs/build-skills). The adapter layout here is tested mechanically; live discovery and media workflow checks must be recorded separately in [validation](../validation.md). Do not infer them from documentation.
