# tools/archive

Finished one-off scripts. Each did a specific job against a specific dataset
and that job is complete. They stay in the repo because they record HOW the
job was done - the endpoints, the payload shapes, the order of operations -
which is worth more than the code itself the next time something similar
comes up.

**Nothing here is maintained.** Most drive the QA Touch browser endpoints
with the pre-2026-08 field names and will need work before they run again.
For the live contract read `docs/QA_TOUCH_INTEGRATION.md`.

| Script | What it did | When |
|---|---|---|
| `migrate_pp_cases_phase_a*.py`, `migrate_pp_cases_phase_b.py` | Moved 214 Partner Portal cases from JlW1 to 70l1, then archived the sources | 2026-06 |
| `reorganize_ldap_cases.py` | Re-filed 175 flat LDAP cases into sub-modules. The only worked example of a module move - which the public API cannot do | 2026-06-26 |
| `build_ota_update_payloads*.py`, `verify_c2c_ota_import.py`, `build_c2c_ota_csv.py`, `build_c2c_rainy_day_csv.py` | Built and verified the C2C OTA import into 60W5 | 2026-06 |
| `build_partner_admin_backfill.py`, `run_partner_admin_backfill.py` | Metadata backfill for the Partner Admin import. Holds the enc_id reference tables | 2026-06 |
| `generate_missing_steps.py` | Generated step JSON for 273 cases that lacked steps. Zero cases lack steps now | 2026-02 |
| `_build_feature_inventory.py` | One-time build of feature_inventory.json | 2026-02 |
| `qatouch_api_discovery.py` | Probed the internal API surface; output is `config/audit_reports/api_endpoint_discovery.json` | 2026-02 |
| `cleanup_ota_steps.py` | Earlier OTA step cleanup | 2026-06 |

To bring one back: copy it up to `tools/`, fix the field names against the
current client, and read the API traps in `docs/QA_TOUCH_INTEGRATION.md`
first.
