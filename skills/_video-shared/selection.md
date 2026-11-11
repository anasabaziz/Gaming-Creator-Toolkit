# Highlight selection and game profiles

## Profiles

| Profile | Preferred events | Necessary context | Framing priorities |
| --- | --- | --- | --- |
| Third-person shooter | Difficult encounters, close escapes, unusual kills, boss finishes | Threat, player response, outcome | Player, target, relevant health/status |
| Top-down action | Skill combinations, chain reactions, large encounters, near-death recoveries | Buildup, ability use, payoff | Surrounding threats, player, relevant HUD |
| Card game | Decisive combos, reversals, unusual interactions, winning turns | Board state, relevant cards/actions, resulting change | Readable board, cards, resources |
| Driving | Overtakes, near misses, sustained drifts, crashes, close finishes | Approach, manoeuvre, outcome | Vehicle, road, competitors, relevant race indicators |
| Party RPG | Dialogue choices, party changes, encounters, rewards and map decisions | Choice, response and visible outcome | Dialogue, party status, board/map and rewards |
| Incremental | Resource gains, upgrades, unlocks and their visible use | Before/after resources and subsequent action | Upgrade options, costs, resources and main action |
| Management / navigation | Trading, deliveries, route choices and progression | Decision, journey/action and outcome | Relevant map, quantities, costs and confirmation |
| General / unfamiliar | Apparent skill use, projectiles, explosions, rapid interactions, dramatic changes and sustained action | Trigger, event, result where visible | Start with full frame; crop only after inspecting |

For other genres begin with the general profile, as requested by the user. Refine it with observed events and user preferences rather than withholding results until a bespoke detector exists.

Store per-game refinements only when useful: profile, preferred events, exclusion cues, context requirements, HUD regions, layout, and user feedback. Distinguish confirmed game rules from inference. Do not invent skill names, achievements, scores, or claims about the player's intent.

## Three analysis passes

### A. Lightweight discovery

Use reduced-resolution frames to measure motion/frame differences, colour/brightness changes, rapid scene changes, audio energy, and low-activity regions. A proposed starting range is 3-6 frames per second for simple feature extraction; benchmark and adjust for the current machine. This is not a requirement to send that many frames to Codex.

Create candidate time windows, padded with context. Large camera pans, screen shake, repetitive attacks and cutscenes can generate misleading activity peaks. Treat menu/loading labels as evidence-based estimates; preserve uncertain regions for review.

### B. Contextual inspection

Extract timestamped sequences showing lead-in, event and aftermath. Codex should inspect actual images, not infer visual content from filenames or motion scores. Review only a bounded selection at a time and record what was observed.

Include coverage outside activity peaks. For card games, prioritise state changes, turn outcomes and readable board/card information even when movement is low. A quiet strategic payoff must not be discarded just because it is less animated than a menu.

If game rules are needed to judge a move, use user-supplied context or explicitly identify the uncertainty. The workflow can identify a visible win without pretending to understand every strategic decision.

### C. Refinement

Inspect denser frame sequences around promising transitions. Use optional OCR for visible victory/defeat text, health, position/lap changes, card text or scores where it helps. Check OCR against frames before making a factual claim.

Sparse sampling can miss brief action. Review candidate previews and refine sampling when evidence is weak; do not claim complete coverage or guaranteed recall.

### Inspection budget and stopping rule

Begin with timestamped overview sheets covering the recording, then inspect a bounded batch of promising regions and profile-relevant quiet regions. Reuse saved observations and images; reopen them when a new decision needs more detail. Use readable contact sheets for comparison and individual frames when text or action cannot be resolved at sheet scale.

Stop expanding discovery once the requested number of distinct, adequately supported candidates covers the user's requested features and profile priorities, with setup/payoff and boundaries checked. This limits additional searching, not required preview or output verification. Expand only to resolve weak evidence, missing feature coverage, repetition, unclear boundaries or user revisions; inspect the relevant ranges first. Return fewer strong candidates when appropriate and disclose sampling limitations. Do not impose a fixed image quota that prevents understanding the footage.

## Candidate ranking

Assess these dimensions separately using a consistent internal scale:
- Event strength: meaningful or visually compelling action.
- Setup/payoff: comprehensible progression and result.
- Readability: action and necessary UI remain understandable.
- Distinctiveness: adds variety relative to other candidates.
- Profile relevance: matches the selected game's criteria.
- Evidence confidence: certainty of interpretation, kept separate from excitement.

Penalise dead time, confusing boundaries, idle menu browsing/loading, repeated events and obstructive effects. Do not penalise meaningful upgrades, rewards, purchases, dialogue or strategic decisions simply because they use a menu. Map requested features/modes to candidate IDs; identify uncovered requirements explicitly. Weights are profile-dependent and must be tuned from examples, not advertised as calibrated probabilities. Scores do not predict virality.

Merge overlapping windows for the same encounter; avoid selecting several versions of the same event. Prefer a diverse shortlist. Return fewer clips when quality is weak and explain why.

## Clip boundaries

Locate the central event, expand backwards for setup, extend through payoff, then trim avoidable waiting. Recommend 30-60 seconds per highlight; explicit user durations take precedence. Explain exceptions needed to preserve a complete event. Do not pad, cut off the result, or remove essential card-game setup just to hit the recommendation.

Default to continuous footage. Intra-clip dead-time removal or non-adjacent montages need a user request or established preference, and should preserve causal order.

## Review and learning

Present candidate ID, start/end times, proposed duration, concise evidence-based reason, confidence/uncertainty and preview. Follow the gameplay-highlights skill's format scope and include the output format, framing reason and readability tradeoffs. For requested vertical output, follow [vertical composition and preview checks](vertical.md). Accept revisions such as starting earlier, retaining the board, rejecting repetitive fights, or keeping only certain IDs.

Record user feedback as per-game preferences where appropriate. A single rejected clip should not create a universal rule for all genres.
