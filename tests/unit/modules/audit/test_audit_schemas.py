import pytest

import app.modules.audit.schemas as schemas_module
from app.modules.audit.schemas import AuditLogEntry, AuditLogListResponse

pytestmark = pytest.mark.unit


def test_audit_log_schema_has_no_hash_input_fields() -> None:
    # Arrange
    # Act: previous_hash/row_hash are trigger-computed, never
    # application-settable — proven by their absence from every schema
    # this module declares, not just AuditLogEntry.
    entry_fields = set(AuditLogEntry.model_fields)
    response_fields = set(AuditLogListResponse.model_fields)

    # Assert
    assert "previous_hash" not in entry_fields
    assert "row_hash" not in entry_fields
    assert "previous_hash" not in response_fields
    assert "row_hash" not in response_fields


def test_audit_log_entry_has_no_inbound_create_or_update_schema() -> None:
    # Arrange
    # Act: no *Create/*Update schema exists anywhere in this module —
    # audit_log writes are internal (self-audit/denial), never
    # router-exposed, which structurally enforces AU-AC4's immutability.
    exported_names = {name for name in dir(schemas_module) if not name.startswith("_")}

    # Assert
    assert not any(name.endswith(("Create", "Update")) for name in exported_names)
