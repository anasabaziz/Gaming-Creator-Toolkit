# Claude Code

Open the standalone toolkit as the project and run:

```text
python scripts/install.py --platform claude
```

This creates `.claude/skills/<name>/SKILL.md` adapters. `CLAUDE.md` points to the shared project guidance in `AGENTS.md`; the skills point to canonical instructions and onboarding. Restart the session if necessary. Ask for customization, then use a skill such as `/gameplay-highlights` or request it in ordinary language.

Keep the full repository: these adapters reference the canonical skills and their Python helpers. They are not single-file upload packages. The installer does not change global Claude settings, permissions or plugins. Configure image generation separately through a supported integration; do not assume Claude Code has a native image-generation tool or the same tool names as another agent. Production can require human listening/GUI checks.

Claude Code documents project skills under `.claude/skills` and the Agent Skills format: [official guide](https://code.claude.com/docs/en/skills). Cloud sessions, account-synced skills and local sessions may load different locations; this package targets a repository-backed session with access to its files/tools. Check the current guide for your mode. Live application validation is tracked [separately](../validation.md).
