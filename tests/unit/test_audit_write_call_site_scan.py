"""AU-AC6/FR-6's CI grep over audit-write call sites, per the story's own
Enforcement Matrix. Runs as a pytest unit test (not a separate CI step) so
it's part of the same `pytest` gate everything else goes through,
mirroring the `roles` module's own `[gate]`-marked CI completeness check
precedent (OD-1).

What this actually guards: a *field-name* regression — someone adding a
new keyword argument to an `AuditLog(...)` call site whose name itself
signals a raw credential (e.g. `password=`, `raw_token=`). It does NOT
inspect the runtime *values* passed to existing fields (e.g. `payload=`
receiving a dict that happens to contain a raw secret) — `AuditLog`'s
column names are fixed by the model, so mypy already blocks an unknown
keyword before this scan would ever see it; the value-shaped case this
scan can't catch is a legitimate field being populated with sensitive
data at a call site, which needs a value-level check if it becomes a real
risk (e.g. asserting `payload=` is built only from known-safe filter
parameters, never a free-text pass-through).

Scoped to this story's own audit-write call sites
(`app/modules/audit/repository.py`'s two `AuditLog(...)` constructions) —
under staged OD-14, no other module's audit-write call site is this
story's to scan; a future OD-14 follow-up repointing an existing module
would need to extend this scan to that module's own repository.py.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# The five value-shapes AU-AC6/FR-6 names as things that must never appear
# in a returned (or written) audit entry.
_FORBIDDEN_KEYWORD_NAMES = frozenset(
    {
        "password",
        "hashed_password",
        "raw_password",
        "token",
        "raw_token",
        "session_cookie",
        "card_number",
        "cvv",
    }
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCANNED_FILE = _REPO_ROOT / "app" / "modules" / "audit" / "repository.py"


def _audit_log_call_keyword_names() -> list[str]:
    tree = ast.parse(_SCANNED_FILE.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AuditLog"
        ):
            names.extend(keyword.arg for keyword in node.keywords if keyword.arg is not None)
    return names


def test_no_secret_shaped_literals_in_audit_write_call_sites() -> None:
    # Arrange
    # Act
    keyword_names = _audit_log_call_keyword_names()

    # Assert: every AuditLog(...) construction site in this story's own
    # write path passes only known-safe field names, never a name that
    # would suggest a raw credential is being written. This is a
    # field-name check only — see module docstring for what it doesn't
    # cover.
    assert keyword_names, "no AuditLog(...) call sites found — scan target may have moved"
    forbidden_used = set(keyword_names) & _FORBIDDEN_KEYWORD_NAMES
    assert not forbidden_used, f"audit write call site names a forbidden field: {forbidden_used}"
