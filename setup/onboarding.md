# First-run customization

This procedure applies before production from any of the five skills, including direct invocation. It does not block reading documentation, planning, installation or tests.

1. Locate the active toolkit project (the directory containing `toolkit.json`). Run `python scripts/configure.py status --skill SKILL_NAME` from that directory. Do not search another creator's parent folders for profiles. An installed adapter points back to this same canonical project.
2. If relevant configuration is missing, tell the user that setup is needed. Ask a short first group: creator/channel name or pseudonym, audience/language, which of the five outputs they want, platforms, and existing tools. Ask follow-ups only for their selected workflows, using the three templates in [templates](../templates/creator-profile.example.md). Do not ask an article-only user to configure trailer styling, or a video-only user to invent a website.
3. For videos/thumbnails ask about sound, text/branding, timing/order, image integration and portrait replacements. For articles ask about voice, examples, CMS, screenshot availability, structure and approved CTAs/disclosures. For everyone discuss output location, verification method, optional review/dashboard and retention. Defaults are suggestions to confirm, not inferred preferences. Optional fields may explicitly be "none", "not used" or "no preference".
4. Summarize the choices, unresolved capabilities and relevant defaults. Obtain the user's confirmation before marking configuration ready. Do not start creator-specific production while this confirmation is pending. Preserve any task brief already supplied.
5. Prepare filled Markdown profiles and an answers JSON in `.creator-toolkit/` (which is ignored by Git). Use the schema below. Record the actual confirmation in `confirmation`; do not invent consent. Run `python scripts/configure.py save --answers .creator-toolkit/answers.json`. This validates the input, writes profiles, hashes them and preserves earlier revisions. The command is an AI/user confirmation record, not proof that a conversation happened.
6. Read the saved profiles before production. `status` checks their hashes and required fields. Changed/removed profiles require reconfirmation, not silent acceptance. Later setup changes preserve unrelated configured workflows. Never copy user answers into public templates or tests.

Example structure (fill these with real confirmed answers, not the literal example):

```json
{
  "schema_version": 1,
  "confirmed": true,
  "confirmation": "The user's actual confirmation of the summarized choices",
  "enabled_skills": ["gameplay-highlights", "gameplay-articles"],
  "profiles": {
    "creator": "Filled creator-profile Markdown",
    "site": "Filled site-profile Markdown",
    "workflow": "Filled workflow-profile Markdown"
  }
}
```

`workflow` is required for all production. `creator` is required for the four visual/video skills; `site` for articles. The user may enable more skills later. Use [doctor](../scripts/doctor.py) for executable discovery; record actual perception/GUI capability separately through the shared preflight. A missing image integration blocks image generation, not article planning. A missing listening method must be handed to a human; it cannot become a fabricated pass.

If dashboard is chosen, install its optional requirements and follow [its guide](../optional/dashboard/README.md). A setup confirmation does not authorize publication, external uploads, subscriptions or automatic schedules. No personal configuration is bundled in a release ZIP.
