# Evidence Warnings / Consistency Report

- Generated: 2026-02-21T18:42:57.047296+00:00
- Git commit: `unknown`

## Dashboard job IDs not found in JSON evidence
These job IDs appear in dashboard markdown(s) but were not found in any JSON evidence file:

- `d0smxp6vx7bg00819cx0`

Recommendation: add `evidence_group_id` and ensure the dashboard MD references the same group + job_id as the JSON artifact.

## JSON evidence missing `shots` field
- manifest.json

## JSON evidence missing `timestamp` field
- files\ultra_secure_qzkp_256bit_results.json
- manifest.json
