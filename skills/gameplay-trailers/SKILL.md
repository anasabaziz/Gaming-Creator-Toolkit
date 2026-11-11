---
name: gameplay-trailers
description: Assemble gameplay highlights or recording excerpts into a trailer, including optional multi-game roundups, sequence, pacing, feature coverage and revisions. Use for montage creation; do not restart highlight discovery or change aspect ratio unless needed by the request.
---

# Gameplay trailers

Before production, follow [first-run customization](../../setup/onboarding.md). Read this project's confirmed relevant profiles in `.creator-toolkit/`; do not treat example templates or another creator's settings as confirmed. Run `python scripts/configure.py status --skill gameplay-trailers` from the toolkit root. If not ready, ask for customization and confirmation before producing deliverables. Planning and installation may continue.

For new production and affected revisions, follow [structured production checks](../_video-shared/review-workflow.md). Use the `trailer` checklist, with criteria for requested duration, feature coverage, sequence, transitions, opening/ending and audio. Capture applicable instructions and production capabilities before substantial work. Separate optional reviewer choice and user acceptance from producer completion according to the local workflow profile.

Follow [whole-job records and recovery](../_video-shared/job-workflow.md). Link feature, sequence, duration and opening/ending requirements to the selected timeline revision. Record dependencies on selected highlights only when used. Reconcile before resuming and use the trailer-coverage case for selection-rule changes.

Follow recording chronology by default. Rearrangement requires the user's request. Preserve original audio and horizontal framing unless overridden. The user's duration controls; do not apply the highlight duration recommendation to a trailer.

Read [shared workflow](../_video-shared/workflow.md). Begin with existing manifests, candidate evidence and validation summaries. Reuse selected ranges; inspect additional source footage only for missing requested features, transitions or unresolved context. A trailer can start directly from a recording without exporting a separate batch of highlights.

Prepare a selection JSON list in source seconds, with reasons/features and evidence. Allocate the requested duration across meaningful scenes; preserve causal order and readable decisions. Use the `trailer` command to create a separate job, set `target_duration`, and check the resulting manifest. Automatic chronology checks reject overlapping/backward ranges; custom ordering must be explicitly requested.

For a recording-only start, run `init` to create its source-only manifest, then `trailer MANIFEST --job NEW_JOB --selections SELECTIONS_JSON`. No populated highlight output or highlight export is required. The derived timeline defaults to original audio; inspect its audio policy, ordering and target duration before rendering.

Before rendering, plan sound at every cut using [audio joins](../_video-shared/composition.md#audio-joins). Preserving original audio means retaining the game's sound; it does not require abrupt cuts. Record each join's output time, treatment (including an intentional hard cut), reason and verification status. Smooth discontinuities where needed without obscuring important cues or changing approved picture timing.

Run the shared render/validation/report commands. Inspect each scene and listen through every join in context, plus the opening and ending, as part of complete-output listening. Revise only affected ranges. Deliver the trailer, timing-editable Shotcut project and timeline/report with actual limitations. Audio repairs must be present in both the export and project; custom post-processing needs fresh validation of those exact outputs. For a vertical trailer, compose the timeline first, then apply `horizontal-to-vertical` while retaining it. Do not add narration, invented captions, music or unrelated effects without a request.

Follow user overrides and project instructions. Planning-only requests end with a plan. Preserve original and approved outputs; publishing and external uploads are separate actions.

Before selecting cuts, record a compact requirements table: feature/mode coverage, exclusions, progression, opening/ending shots, duration, audio, source ranges and verification status. Reconcile actual source-edit duration with the request; do not silently expand an existing edit. Check the final timeline against this table and keep approved requirements through revisions.

For optional multi-game roundups, read [composition](../_video-shared/composition.md). Plan source IDs, ordering, per-game timing, labels, opening/closing artwork and requested music in a storyboard. Custom ordering can come from the current request or an applicable local profile; record its basis. Retain music attribution. Reference-video styling does not authorize copying its assets or audio.

For authorised portrait replacements, choose alternate ranges using the original coverage/progression/ending requirements, then hand the revised timeline to horizontal-to-vertical. Record changed ranges and reasons; do not rerun broad discovery. Read any applicable local creator profile for repeat preferences. Titles, labels and music remain optional in public workflows.

Mark each coverage requirement as user-required or producer-selected, with its source and selected segments. During revisions, account for kept/replaced/dropped features and explain tradeoffs; replacement permission does not waive user-required coverage. Use the optional structured `feature_coverage` ledger in [shared workflow](../_video-shared/workflow.md) for mechanical checks.

When a local job dashboard is configured, follow [dashboard tracking](../_video-shared/dashboard-workflow.md) at resumption and before delivery. Preserve exact-revision human attestations and durable history independently of removable job files.