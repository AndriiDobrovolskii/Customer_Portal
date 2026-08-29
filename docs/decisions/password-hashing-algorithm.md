# Decision: Password Hashing Algorithm — Argon2id

**Date:** 2026-08-29
**Status:** Resolved
**Decided by:** Project owner, via interactive decision during docs/skills alignment work

## Context

Two authoritative sources disagreed on the password-hashing algorithm:

- `AGENTS.md` §2 (Tech Stack) and `docs/ARCHITECTURE.md` named **bcrypt** (`bcrypt>=4.1`), and it was already implemented and shipped in `app/core/security.py` as part of US-001 (Register User).
- The stories `docs/stories/US-2.1-login.md`, `US-2.4-password-reset.md`, and `US-2.5-mfa-totp.md` each deliberately specified **Argon2id** in their own Assumptions & Defaults tables — e.g. US-2.1's "Password hashing cost | Argon2id tuned to ≈100 ms | Balance between brute-force resistance and endpoint latency" — and the specifications derived from them (`US-005`, `US-008`, `US-009`) carried that choice through.

This was flagged as BR-003 in `docs/product/business-rules.md` while `docs/product/*.md` was being authored, since a business-rules doc can't state a fact two ways.

## Decision

**Argon2id is canonical**, project-wide, for every credential hash (passwords and MFA recovery codes). It is memory-hard and more resistant to GPU/ASIC brute-force than bcrypt, and it is what the product requirements (the stories) actually asked for — bcrypt was the value carried in the engineering scaffold, not a deliberate product decision.

## Consequences

The already-shipped US-001 implementation used bcrypt and had to be changed, not just documented around:

- `pyproject.toml`: `bcrypt>=4.1` → `argon2-cffi>=23.1`.
- `app/core/security.py`: `bcrypt.hashpw()` → `argon2.PasswordHasher.hash()`.
- `app/core/config.py`: `bcrypt_rounds` → `argon2_time_cost` / `argon2_memory_cost_kb` / `argon2_parallelism` (defaults: 3 / 65536 / 4, argon2-cffi's own recommended defaults — not yet empirically tuned to the stories' "≈100 ms" target; re-tune once real hardware numbers are available).
- `.env.example`: `BCRYPT_ROUNDS` → the three `ARGON2_*` settings.
- `tests/integration/modules/users/test_users_router.py`: the persisted-hash assertion now checks for the `$argon2id$` prefix instead of bcrypt's `$2b$`.
- `AGENTS.md` §2, §3.5, §7 and `docs/ARCHITECTURE.md` (tech stack table, package-structure comment, async-offload example, `Settings` example, security addenda): all bcrypt references replaced.
- `users.hashed_password` (`String(255)`) needed no migration — an Argon2id hash with these parameters is ~97 characters.

No spec required a change; `US-005`, `US-008`, `US-009` were already correct.
