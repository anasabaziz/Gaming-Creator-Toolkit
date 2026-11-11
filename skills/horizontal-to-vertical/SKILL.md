---
name: horizontal-to-vertical
description: Convert an existing horizontal gameplay clip or trailer to portrait using reviewed crops or synchronized panels. Use only for explicitly requested vertical or 9:16 output, preserving the existing edit timing unless the user or an applicable local profile authorises replacements.
---

# Horizontal to vertical

Before production, follow [first-run customization](../../setup/onboarding.md). Read this project's confirmed relevant profiles in `.creator-toolkit/`; do not treat example templates or another creator's settings as confirmed. Run `python scripts/configure.py status --skill horizontal-to-vertical` from the toolkit root. If not ready, ask for customization and confirmation before producing deliverables. Planning and installation may continue.

For new production and affected revisions, follow [structured production checks](../_video-shared/review-workflow.md). Use the `vertical` checklist and record full-interval framing coverage against the final export, including essential action, HUD, dialogue, transitions and any authorized replacements. Sampled images cannot satisfy full-interval review. Follow the local workflow profile for optional post-delivery reviewer choice and separate acceptance.

Follow [whole-job records and recovery](../_video-shared/job-workflow.md). Record the parent timeline revision, crop/panel decisions, replacement authorization and unresolved framing issues. Tie full-interval review evidence to the exact exported revision. Use the vertical-hud case when evaluating framing-rule changes.

Keep horizontal output unless vertical conversion is explicitly requested. Generic highlights, shorts or social-video requests do not imply portrait conversion.

Read [vertical composition and full-segment checks](../_video-shared/vertical.md) and the relevant commands in [shared workflow](../_video-shared/workflow.md). Begin with the existing approved manifest and source evidence. Preserve source ranges, sequence and timing in reframing-only mode. When the request or applicable local creator profile authorises replacements, use the trailer skill to choose suitable alternatives, preserve duration and required coverage/progression/ending, and record the changed ranges and reasons. Do not repeat broad discovery.

Inspect each segment's full framing. Choose a stable crop or synchronized panels retaining essential action, HUD and dialogue, with no added bars or background-fill substitutes. When a single crop loses essential UI, consider separately cropped HUD regions in compact rows around the main gameplay, including side-by-side panels where useful. Use the supported rows layout for independently cropped side-by-side HUD panels; check exact canvas coverage and readability. Record a layout for every segment and the user request authorizing conversion. Use `vertical` to create a separate job; review its manifest before rendering.

Create a lower-resolution preview job with equivalent geometry when it will resolve layout/readability uncertainty or avoid a costly final render. Record that purpose; skip it when it adds no useful evidence. Review the entire preview when used, and always review framing throughout the final 1080 x 1920 export, especially layout changes and scene transitions. Automated sample comparisons do not replace final full-interval review.

The shared renderer supports static crops, stacked/row panels and optional image/title effects described in [composition](../_video-shared/composition.md). Shotcut timing is editable; framing/effects are baked into cached segment media. Revise the manifest to change them. Native editable effect filters and moving crop tracking remain unsupported. This reusable approach aims to reduce repeated scripting; do not claim measured token savings without comparison data.

Deliver the MP4, project and report, identifying editability and review limitations. Preserve approved files and original audio unless overridden. If a readable portrait composition cannot be achieved, explain the conflict before finalizing.

Bind the conversion to the latest intended parent revision, including any separately repaired audio. Reframing must preserve its fades, overlaps, mix and sync rather than rebuilding hard-cut audio from raw source ranges. Record the audio dependency explicitly and check transitions in the final portrait export and project. Authorized shot replacements require reassessing affected sound joins; an earlier parent audio pass does not cover changed audio.

Check the existing edit's actual duration before conversion. Clarify a conflicting requested duration rather than padding or silently shortening. Closing reveals are enabled only by the request or an applicable local profile, with supplied artwork identified for that purpose. Preserve the payoff before the reveal; keep artwork sharp and proportional. Intentional blur behind a requested reveal is allowed; blurred filler to occupy unused portrait space is not.

For authorized replacements, distinguish user-required coverage from producer-selected variety and record kept/replaced/dropped features. Follow the coverage ledger and panel-seam checks in [vertical guidance](../_video-shared/vertical.md), including transient text, screen shake and modal changes.

When a local job dashboard is configured, follow [dashboard tracking](../_video-shared/dashboard-workflow.md) at resumption and before delivery. Preserve exact-revision human attestations and durable history independently of removable job files.