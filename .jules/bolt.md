# Bolt Journal ⚡

Critical performance learnings and architecture notes.

## 2026-11-03 - High-Frequency PyWebView Polling DOM Teardowns
**Learning:** PyWebView polls `get_matrix_state()` every 200ms (5Hz). Rebuilding `grid.innerHTML` and `tbody.innerHTML` unconditionally on every poll causes continuous layout recalculations/reflows and tears down active CSS flash animations (`pulse-flash`) before they can complete.
**Action:** Always maintain a compact signature/fingerprint (`sigKey`) of active items. If state hasn't changed between polls, skip DOM teardown and return immediately.
