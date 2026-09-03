import uuid
from datetime import UTC, datetime, timedelta

import pytest

from scripts.verify_audit_chain import GENESIS_SENTINEL, ChainRow, verify_chain

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _row(
    *,
    occurred_at: datetime,
    previous_hash: str,
    row_hash: str,
    expected_row_hash: str | None = None,
    event: str = "audit_log_viewed",
) -> ChainRow:
    return ChainRow(
        id=uuid.uuid4(),
        occurred_at=occurred_at,
        event=event,
        previous_hash=previous_hash,
        row_hash=row_hash,
        expected_row_hash=expected_row_hash if expected_row_hash is not None else row_hash,
    )


def test_verify_chain_empty_list_is_intact() -> None:
    # Act & Assert
    assert verify_chain([]) is None


def test_verify_chain_single_row_seeded_from_genesis_is_intact() -> None:
    # Arrange
    row = _row(occurred_at=_FIXED_NOW, previous_hash=GENESIS_SENTINEL, row_hash="hash-1")

    # Act & Assert
    assert verify_chain([row]) is None


def test_verify_chain_multi_row_correctly_linked_is_intact() -> None:
    # Arrange
    row1 = _row(occurred_at=_FIXED_NOW, previous_hash=GENESIS_SENTINEL, row_hash="hash-1")
    row2 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=1), previous_hash="hash-1", row_hash="hash-2"
    )
    row3 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=2), previous_hash="hash-2", row_hash="hash-3"
    )

    # Act & Assert
    assert verify_chain([row1, row2, row3]) is None


def test_verify_chain_detects_break_in_hash_sequence() -> None:
    # Arrange: row2's previous_hash doesn't match row1's row_hash
    row1 = _row(occurred_at=_FIXED_NOW, previous_hash=GENESIS_SENTINEL, row_hash="hash-1")
    row2 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=1),
        previous_hash="wrong-previous-hash",
        row_hash="hash-2",
    )

    # Act
    result = verify_chain([row1, row2])

    # Assert
    assert result is not None
    assert result.id == row2.id
    assert result.reason == "previous_hash_mismatch"


def test_verify_chain_detects_tampered_row_fields() -> None:
    # Arrange: row_hash doesn't match the recomputed expected_row_hash —
    # simulates a row whose event/actor_id/etc. was altered in place after
    # insertion, without touching previous_hash.
    row1 = _row(occurred_at=_FIXED_NOW, previous_hash=GENESIS_SENTINEL, row_hash="hash-1")
    tampered_row2 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=1),
        previous_hash="hash-1",
        row_hash="hash-2",
        expected_row_hash="recomputed-different-hash",
        event="tampered",
    )

    # Act
    result = verify_chain([row1, tampered_row2])

    # Assert
    assert result is not None
    assert result.id == tampered_row2.id
    assert result.event == "tampered"
    assert result.reason == "row_hash_mismatch"


def test_verify_chain_first_row_not_seeded_from_genesis_is_a_break() -> None:
    # Arrange: the very first row in the chain must seed from the sentinel,
    # not an arbitrary value.
    row = _row(occurred_at=_FIXED_NOW, previous_hash="not-the-sentinel", row_hash="hash-1")

    # Act
    result = verify_chain([row])

    # Assert
    assert result is not None
    assert result.reason == "previous_hash_mismatch"


def test_verify_chain_returns_first_break_only() -> None:
    # Arrange: two independent breaks; only the first is reported.
    row1 = _row(occurred_at=_FIXED_NOW, previous_hash=GENESIS_SENTINEL, row_hash="hash-1")
    broken_row2 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=1),
        previous_hash="wrong",
        row_hash="hash-2",
    )
    broken_row3 = _row(
        occurred_at=_FIXED_NOW + timedelta(seconds=2),
        previous_hash="also-wrong",
        row_hash="hash-3",
    )

    # Act
    result = verify_chain([row1, broken_row2, broken_row3])

    # Assert
    assert result is not None
    assert result.id == broken_row2.id
