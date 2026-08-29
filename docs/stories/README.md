# Backlog

Stories are the source of truth for scope; specifications are generated from them
(`story-spec-writer` → `docs/specifications/`), then audited (`story-spec-reviewer`
→ `docs/reviews/`).

| Story | Feature | AC prefix | Status |
|---|---|---|---|
| [US-1.1](US-1.1-register-user.md) | Register User | `AC-` | Spec + review complete (US-001) |
| [US-1.2](US-1.2-verify-email.md) | Verify Email | `VE-AC` | Spec + review complete (US-002) |
| [US-1.3](US-1.3-update-profile.md) | Update Profile | `UP-AC` | Spec + review complete (US-003) |
| [US-1.4](US-1.4-deactivate-account.md) | Deactivate Account | `DA-AC` | Spec + review complete (US-004) |
| [US-2.1](US-2.1-login.md) | Login | `LI-AC` | Spec + review complete (US-005) |
| [US-2.2](US-2.2-logout.md) | Logout | `LO-AC` | Spec + review complete (US-006) |
| [US-2.3](US-2.3-refresh-token.md) | Refresh Token | `RT-AC` | Spec + review complete (US-007) |
| [US-2.4](US-2.4-password-reset.md) | Password Reset | `PR-AC` | Spec + review complete (US-008) |
| [US-2.5](US-2.5-mfa-totp.md) | MFA (TOTP) | `MF-AC` | Spec + review complete (US-009) |
| [US-2.6](US-2.6-active-sessions.md) | Active Session Management | `SM-AC` | Spec + review complete (US-010) |
| [US-3.1](US-3.1-manage-users.md) | Manage Users (5 slices) | `MU-AC` | Spec + review complete (US-011) |
| [US-3.2](US-3.2-manage-roles.md) | Manage Roles | `MR-AC` | Spec + review complete (US-012) |
| [US-3.3](US-3.3-view-audit-information.md) | View Audit Information | `AU-AC` | Spec + review complete (US-013) |
| [US-4.1](US-4.1-create-ticket.md) | Support Tickets (create) | `ST-AC` | Spec + review complete (US-014) |
| [US-4.2](US-4.2-ticket-replies.md) | Ticket Replies | `TR-AC` | Spec + review complete (US-015) |
| [US-4.3](US-4.3-ticket-resolution.md) | Ticket Resolution | `TC-AC` | Spec + review complete (US-016) |

Cross-cutting conventions, personas and the eleven recorded decisions for Epics 2–4
live in the epic-level document `epic-2-3-4-user-stories.md` (see the project root
of this Drive folder / the chat this backlog was produced in). Each story above
restates only what it changes from those conventions.

**Dependency notes:**
- US-2.5 depends on US-2.1 and US-3.2 (permission scopes).
- US-2.6 depends on US-2.3 (reads the refresh-token family metadata it writes).
- US-3.1 depends on US-1.4 (DA-AC10 invariant) and US-3.2 (permission scopes).
- US-3.3 depends on US-3.2 (`audit:read` scope).
- US-4.1 is blocked by an as-yet-unwritten attachment-upload story.
- US-4.2 depends on US-4.1; US-4.3 depends on US-4.1 and US-4.2.

**Suggested build order:** US-3.2 first (everything else checks its scopes), then
US-2.1 → US-2.3 → US-2.2, then US-3.1, US-3.3, US-2.6, US-2.5, then Epic 4 once the
attachment-upload story is scheduled.