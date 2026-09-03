# Security Review: Active Session Management (US-2.6 / spec US-2.6)

**Story ID:** US-2.6
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass

## Summary

This story introduces no new credential storage, no new inbound schema, and no raw SQL — its security surface is a read path (session listing, with geo-IP/device-label derivation from already-stored `ip`/`user_agent` data) and a revocation path reusing US-2.2's existing mechanism. All six AGENTS.md §7 non-negotiable rules are satisfied; two Low-severity advisory findings are noted (neither forces a Fail).

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A — Pass | This story touches no password-handling code path; no credential is stored, read, or verified anywhere in `service.py`'s new methods (`list_sessions`, `revoke_session`, `_evict_oldest_family_if_at_cap`) or `repository.py`'s new queries. |
| No plaintext/reversible encryption for credentials | N/A — Pass | Same reasoning — no credential-like field is introduced (`family_id`, `ip`, `user_agent`, `created_at`, `last_used_at`, `device_label`, `location` are none of them credentials). |
| No tokens/hashes/PII in logs; no `print()` | Pass | The only new logging call is `app/core/geoip.py:29`'s `logger.info("GeoLite2 database not available at %s; ...", settings.geoip_database_path)` — logs a config file path, not a token, hash, IP, or any request-derived value. `grep -rn "print("` across all files touched by this story returns nothing. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A — Pass | Neither new endpoint (`GET /auth/sessions`, `DELETE /auth/sessions/{family_id}`) has a request body (confirmed in `docs/designs/api/US-2.6-openapi.yaml`); `SessionEntry`/`SessionListResponse` (`schemas.py`) are outbound-only, so the inbound-schema rule doesn't apply to this story's new schemas. |
| Parameterized SQL only, no string interpolation | Pass | Every new `repository.py` query (`get_any_refresh_token_for_family`, `lock_live_refresh_tokens_for_user`, `list_live_families_for_user`, `get_family_created_at_map_for_user`) uses `select()`/`.where()`/`.group_by()` SQLAlchemy Core constructs with bound Python values — no f-string or `%`-interpolated SQL. Both migrations (`5dccea7a3749`, `db8cbd5e3697`) use `op.add_column`/`op.create_index`/`op.drop_column`/`op.drop_index` exclusively — no hand-written `op.execute()` with raw SQL. |
| Uniform auth-failure response, no differentiation leaked | Pass | `revoke_session` (`service.py:887-...`) folds "belongs to a different user" and "malformed/nonexistent `family_id`" into the identical `SessionNotFoundError` (404, `not-found`) via one shared ownership check (`get_any_refresh_token_for_family`) — confirmed by `test_revoke_session_other_users_family_returns_404` and `test_revoke_session_malformed_family_id_returns_404` asserting the same status/type. `list_sessions`/`revoke_session`'s `401` path is the pre-existing, shared `get_authenticated_user`/`CurrentUserDep` mechanism, unchanged by this story. |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] Regex-based User-Agent parsing on fully attacker-controlled input** — `app/core/device.py`'s `resolve_device_label` calls the `user-agents` library (backed by `ua-parser`'s regex patterns) on the raw `User-Agent` header of every stored refresh-token row, on every `GET /v1/auth/sessions` call (up to 20 parses per request, per the live-session cap). The `User-Agent` header is fully attacker-controlled at request time (and persisted verbatim at login, unchanged since US-2.1). `ua-parser`'s regex set is widely used and not currently known to have a catastrophic-backtracking pattern, but this story is the first to invoke it on this codebase's stored, attacker-supplied data at read time rather than write time — worth a periodic dependency-advisory check (e.g. Dependabot/`pip-audit`) rather than a code change here.
- **[Low] `geoip_database_path` is an operator-controlled config value, not request-controlled, but shares this project's one existing local-file-path setting pattern** — `app/core/geoip.py`'s `geoip2.database.Reader(settings.geoip_database_path)` opens whatever path `get_settings()` resolves. This is the identical trust model as the pre-existing `breached_password_list_path` setting (US-2.4) — an environment/deploy-time value, never client input — so this isn't a new risk class, just worth noting alongside it for anyone auditing "what file paths does this app open from config."

## Verdict Rationale

Pass: all six §7 rows are Pass (three of them N/A because this story introduces no credential-handling or inbound-schema surface, which is itself the correct outcome for a read/revoke story with no new request body). Both advisory findings are Low-severity, pre-existing-pattern-consistent, and do not affect the verdict.
