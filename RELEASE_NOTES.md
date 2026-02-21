# Release Notes

## v1.5.0 - 2026-02-21

### Added
- `/version` command for users.
- `/announce_update` admin command for sending update announcements to all users.

### Fixed
- Postgres type mismatch in daily lesson mistake joins (`text` vs `bigint`).
- Daily lesson topic rotation reliability and grammar coverage tracking.
- Daily lesson quiz double-click race condition.
- `/start` flow UI buildup (stale intro/menu messages).
- Dictionary level/letter pagination stability on Postgres.

### Operations
- Broadcast queue claim/recovery hardening.
- Persistent FSM storage in DB for multi-replica webhook safety.
