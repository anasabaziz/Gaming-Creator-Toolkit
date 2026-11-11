# Optional job dashboard

This portable dashboard runs locally without AI/API calls, macros, Node or vendor runtime libraries. It uses Python and openpyxl. Excel or LibreOffice can edit the workbook; application round-trip checks are part of release validation.

From the toolkit root:

```text
python -m pip install -r optional/dashboard/requirements.txt
python optional/dashboard/job_dashboard.py
```

This creates `tracking/Creator Job Dashboard.xlsx` and durable `tracking/records/` locally. Both are excluded from public releases. Default discovery scans `jobs/`. To change it, copy [config.example.json](config.example.json) to `tracking/config.json` and set `scan_folders`; paths are relative to the toolkit root. `game_names` maps folder-name fragments to display names; `job_metadata` can override a job ID's `game`, `request_date` and `date_source`. Dates default to UTC.

The Dashboard tab shows a snapshot at refresh. Deliverables contains exact revision packages, their full human checklist and outstanding conditions. Edit only yellow columns E:H: human review, acceptance, file disposition and feedback. Do not insert/delete rows or change generated fields. Sorting complete table rows is supported. Read long checklists using the formula bar/expanded row; do not assume visible clipped text is the whole checklist.

Select **Passed - all listed checks performed** only after performing every displayed method on every named target in full. Save and close the workbook, then rerun the command. Refresh preserves the saved workbook as attestation evidence, imports decisions by stable record ID and checks the journal. A human pass cannot replace automated validation/project comparison or unresolved production conditions. Acceptance is separate and does not imply a performed review. Never have an AI choose Passed for you.

The helper stops on invalid input, changed generated cells, a lock or damaged journal. Keep evidence and diagnose the issue. A known Excel/LibreOffice lock prevents refresh; always close other spreadsheet editors too. A failed rebuild preserves captured decisions in `tracking/records/`; rerun after resolving the failure. `--no-build` updates JSON records only.

Retain `tracking/` outside removable job directories. Missing media stays listed as unavailable; history is not a media backup. Save/close/refresh before any user-initiated disposal to bind attestations while targets still exist. The helper never deletes media or recreates missing jobs. Do not copy this generated directory into a public repository.

To use tracking in production, record the refresh command in the confirmed workflow profile. Shared checks explain how producers register journals/contracts before refresh. Maintenance and planning do not require dashboard jobs.
