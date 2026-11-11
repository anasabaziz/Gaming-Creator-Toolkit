# Working-file retention

## Archive verification

Run from project root (replace paths). These commands never copy, upload or delete:

```text
python skills/_video-shared/archive_verify.py inventory JOB_FOLDER --job-record JOURNAL --extra ADDITIONAL_DEPENDENCY --out INVENTORY.json
python skills/_video-shared/archive_verify.py verify INVENTORY.json DESTINATION --out VERIFICATION.json
python skills/_video-shared/cleanup_audit.py JOB_FOLDER --job-record JOURNAL --out DEPENDENCIES.json
```

Write reports outside the inventoried tree to avoid self-inclusion on later runs. The inventory includes job-tree files, known MLT/manifest references, journal-registered identities and explicitly added dependencies; investigate unknown references. Add profiles, reference library, supplied artwork/fonts/music and any other outside dependencies explicitly. It excludes `.env` files; review the inventory for private material before any separately authorized copy. External files receive deterministic `external/` destinations; this does not relink MLTs automatically.

Register the reports through `job_state.py archive JOB --data PAYLOAD.json`, with payload `{"id":"archive-1","path":"VERIFICATION.json"}`. The verification report compares destination hashes with the inventory and checks whether MLT references stay inside the destination. A passed copy is not proof of independent storage or restoration. Open representative restored projects, seek/play with sources unavailable at original paths, test final playback, and register exact-revision evidence as artifacts plus a journal event. Preserve the original archive inventory; if a restore copy needs relinking, record that derived project and its changed hash separately.

Keep backup status separate from content completion unless archiving is requested. No actual backup is established until destination, preservation scope, copy verification and appropriate restore checks are documented. No automatic backup scheduling is introduced.

Do not remove working files automatically. Ask what must remain possible: playback of final exports, Shotcut timing edits, or full reframing/reselection/re-rendering.

- Playback: verified final MP4s are self-contained. Keep accepted thumbnail files, article packages and music credits separately.
- Timing edits: keep each MLT and every referenced media/art/audio/project file. Relative paths must retain their directory structure; absolute paths need relinking after a move. An MLT alone is not a backup.
- Full revisions: additionally keep original recordings, supplied artwork/fonts/music, manifests, replacement history, observations and toolkit version. Cached renders cannot recover discarded original footage or unbaked artwork.
- Regenerable evidence, previews, obsolete revisions and caches may be candidates only after checking references and confirming that the user no longer needs that revision. Files named media, preview or temporary are not inherently disposable: some projects reference them directly.

Use `python _video-shared/cleanup_audit.py WORKSPACE --out REPORT.json` for a read-only inventory of MLT references, existing/missing dependencies and directory sizes. It never deletes files. Its references cover parsed MLT resources, not all possible external script/runtime dependencies. Unknown/missing resources and parse failures must be investigated before cleanup; the report is not deletion authorization.

Before removing local copies, copy the intended archive elsewhere, verify hashes/byte counts, and open representative projects from the archive with their media linked. Test final playback separately. Back up the private creator/site profiles and reference library independently of the public skill distribution. Do not assume a cloud-synced folder is an independent backup: deleting synced files can propagate.
