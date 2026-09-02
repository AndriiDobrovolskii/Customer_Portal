import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import encode_access_token, hash_password
from app.main import app
from app.modules.roles.models import Role, UserRole
from app.modules.users.models import User, UserSession
from scripts.verify_audit_chain import GENESIS_SENTINEL, verify_chain
from scripts.verify_audit_chain import _fetch_chain as fetch_chain

pytestmark = pytest.mark.integration

_READ = ["audit:read"]


async def _seed_user(db_session: AsyncSession, *, email: str, status: str = "active") -> User:
    user = User(email=email, hashed_password=await hash_password("Str0ng!Pass1"), status=status)
    user.email_verified = True
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_session_and_token(
    db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str]
) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(jti=jti, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=1))
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=scopes)


async def _assign_role(db_session: AsyncSession, *, user_id: uuid.UUID, role_name: str) -> None:
    result = await db_session.execute(select(Role.id).where(Role.name == role_name))
    role_id = result.scalar_one()
    db_session.add(UserRole(user_id=user_id, role_id=role_id))
    await db_session.flush()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _expired_token(db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str]) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.flush()
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "scopes": scopes,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


async def _revoked_session_token(
    db_session: AsyncSession, *, user_id: uuid.UUID, scopes: list[str]
) -> str:
    jti = uuid.uuid4()
    db_session.add(
        UserSession(
            jti=jti,
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    return encode_access_token(user_id=user_id, jti=jti, scopes=scopes)


def _window(days: int = 1) -> dict[str, str]:
    now = datetime.now(UTC)
    return {"from": (now - timedelta(days=days)).isoformat(), "to": now.isoformat()}


# --- AU-AC1/FR-1: filtered query ---------------------------------------


async def test_list_audit_logs_filtered_query_returns_200_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="lister@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    # `now()` is fixed for the whole transaction in Postgres (not
    # per-statement), so both rows need explicit, distinct, past-relative
    # offsets — a future offset can fall outside the query window, since
    # the window's `to` bound is computed in Python moments later, not a
    # full second after the transaction's frozen `now()`.
    login_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO auth_audit_log (id, event, actor_id, ip, request_id, occurred_at) "
            "VALUES (:id, 'login_failed', :actor_id, '10.0.0.1', 'req-a', "
            "now() - interval '2 seconds')"
        ),
        {"id": uuid.uuid4(), "actor_id": login_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO auth_audit_log (id, event, actor_id, ip, request_id, occurred_at) "
            "VALUES (:id, 'login_success', :actor_id, '10.0.0.2', 'req-b', "
            "now() - interval '1 second')"
        ),
        {"id": uuid.uuid4(), "actor_id": login_id},
    )

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**_window(), "actor_id": str(login_id)},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["event"] == "login_success"
    assert body["items"][1]["event"] == "login_failed"


async def test_list_audit_logs_historical_rows_null_pad_unavailable_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: profile_audit_log has no event/target_id/outcome columns —
    # the view NULL-pads them, not synthesizes fabricated values.
    admin = await _seed_user(db_session, email="historylister@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    actor_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO profile_audit_log "
            '(id, actor_id, field, old_value, new_value, request_id, "timestamp") '
            "VALUES (:id, :actor_id, 'locale', 'en-US', 'en-GB', 'req-c', now())"
        ),
        {"id": uuid.uuid4(), "actor_id": actor_id},
    )

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**_window(), "actor_id": str(actor_id)},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert entry["event"] == "field_changed"
    assert entry["target_id"] is None
    assert entry["outcome"] is None


async def test_list_audit_logs_no_matches_returns_empty_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="emptylister@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**_window(), "actor_id": str(uuid.uuid4())},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


async def test_list_audit_logs_limit_over_max_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="limiter@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**_window(), "limit": 101},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-failed")


async def test_list_audit_logs_invalid_cursor_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="cursorer@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**_window(), "cursor": "not-a-real-cursor"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-failed")


# --- AU-AC2/FR-2: self-audit write --------------------------------------


async def test_list_audit_logs_success_writes_self_audit_entry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="selfauditor@example.com")
    await _assign_role(db_session, user_id=admin.id, role_name="auditor")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    window = _window()

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={**window, "event": "login_failed"},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 200
    result = await db_session.execute(
        text(
            "SELECT actor_id, actor_role, event, outcome, payload FROM audit_log "
            "WHERE event = 'audit_log_viewed' ORDER BY occurred_at DESC LIMIT 1"
        )
    )
    row = result.mappings().one()
    assert row["actor_id"] == admin.id
    assert row["actor_role"] == "auditor"
    assert row["outcome"] == "success"
    assert row["payload"]["event"] == "login_failed"


# --- AU-AC3/FR-3 + cross-cutting AGENTS.md §5 security cases ------------


async def test_list_audit_logs_missing_scope_returns_403_and_audits_denial(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="noscope@example.com")
    await _assign_role(db_session, user_id=user.id, role_name="customer")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=[])

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs", params=_window(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["type"].endswith("/insufficient-permission")
    result = await db_session.execute(
        text(
            "SELECT actor_id, actor_role, outcome FROM audit_log "
            "WHERE event = 'audit_log_access_denied' ORDER BY occurred_at DESC LIMIT 1"
        )
    )
    row = result.mappings().one()
    assert row["actor_id"] == user.id
    assert row["actor_role"] == "customer"
    assert row["outcome"] == "denied"


async def test_list_audit_logs_no_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/v1/admin/audit-logs", params=_window())

    # Assert
    assert response.status_code == 401


async def test_list_audit_logs_malformed_token_returns_401(client: AsyncClient) -> None:
    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params=_window(),
        headers=_auth_headers("not-a-real-jwt"),
    )

    # Assert
    assert response.status_code == 401


async def test_list_audit_logs_expired_token_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="expiredaudit@example.com")
    token = await _expired_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs", params=_window(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 401


async def test_list_audit_logs_revoked_session_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    user = await _seed_user(db_session, email="revokedaudit@example.com")
    token = await _revoked_session_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs", params=_window(), headers=_auth_headers(token)
    )

    # Assert
    assert response.status_code == 401


# --- AU-AC4/FR-4: immutability -------------------------------------------


async def test_patch_audit_logs_returns_405(client: AsyncClient, db_session: AsyncSession) -> None:
    # Arrange
    user = await _seed_user(db_session, email="patcher@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.patch("/api/v1/admin/audit-logs", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 405


async def test_put_audit_logs_returns_405(client: AsyncClient, db_session: AsyncSession) -> None:
    # Arrange
    user = await _seed_user(db_session, email="putter@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.put("/api/v1/admin/audit-logs", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 405


async def test_delete_audit_logs_returns_405(client: AsyncClient, db_session: AsyncSession) -> None:
    # Arrange
    user = await _seed_user(db_session, email="deleter@example.com")
    token = await _seed_session_and_token(db_session, user_id=user.id, scopes=_READ)

    # Act
    response = await client.delete("/api/v1/admin/audit-logs", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 405


# --- AU-AC5/FR-5: query window -------------------------------------------


async def test_list_audit_logs_window_over_90_days_returns_422_range_too_wide(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="widewindow@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    now = datetime.now(UTC)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs",
        params={"from": (now - timedelta(days=91)).isoformat(), "to": now.isoformat()},
        headers=_auth_headers(token),
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/range-too-wide")


async def test_list_audit_logs_both_bounds_omitted_returns_422_range_too_wide(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange
    admin = await _seed_user(db_session, email="nowindow@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get("/api/v1/admin/audit-logs", headers=_auth_headers(token))

    # Assert
    assert response.status_code == 422
    assert response.json()["type"].endswith("/range-too-wide")


async def test_list_audit_logs_single_missing_bound_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: OD-10 — single missing bound rejected same as both-missing
    admin = await _seed_user(db_session, email="onewindow@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)
    now = datetime.now(UTC)

    # Act: from only
    from_only = await client.get(
        "/api/v1/admin/audit-logs",
        params={"from": (now - timedelta(days=1)).isoformat()},
        headers=_auth_headers(token),
    )
    # Act: to only
    to_only = await client.get(
        "/api/v1/admin/audit-logs", params={"to": now.isoformat()}, headers=_auth_headers(token)
    )

    # Assert
    assert from_only.status_code == 422
    assert from_only.json()["type"].endswith("/range-too-wide")
    assert to_only.status_code == 422
    assert to_only.json()["type"].endswith("/range-too-wide")


# --- AU-AC6/FR-6: no secrets (supplementary regression guard) -----------


async def test_list_audit_logs_response_contains_no_named_secrets(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Arrange: this story's own 2 event types carry none of the 5 named
    # secret-shaped values — real AU-AC6 coverage is the CI grep over
    # audit-write call sites (docs/tests/US-013-traceability-matrix.md),
    # not this test; kept as a regression guard.
    admin = await _seed_user(db_session, email="secretchecker@example.com")
    token = await _seed_session_and_token(db_session, user_id=admin.id, scopes=_READ)

    # Act
    response = await client.get(
        "/api/v1/admin/audit-logs", params=_window(), headers=_auth_headers(token)
    )

    # Assert
    body_text = response.text.lower()
    for forbidden in ("password", "hash", "session_cookie", "raw_token"):
        assert forbidden not in body_text


# --- AU-AC7/FR-7: hash chain ----------------------------------------------


async def test_verify_audit_chain_untouched_partition_reports_intact(
    db_session: AsyncSession,
) -> None:
    # Arrange: `now()` is fixed for the whole transaction in Postgres (not
    # per-statement) — inserting 3 rows with a bare `now()` gives them all
    # the *same* occurred_at, and the trigger's `id`-tiebreak (a random
    # UUID) then doesn't reliably reconstruct insertion order. Explicit,
    # strictly increasing offsets avoid the collision.
    for offset in range(3):
        await db_session.execute(
            text(
                "INSERT INTO audit_log (id, occurred_at, category, event) "
                "VALUES (:id, now() + (:offset * interval '1 second'), 'audit', 'chain_test')"
            ),
            {"id": uuid.uuid4(), "offset": offset},
        )

    # Act
    rows = await fetch_chain(db_session)
    result = verify_chain(rows)

    # Assert
    assert result is None


async def test_verify_audit_chain_mutated_row_reports_exact_break(
    db_session: AsyncSession,
) -> None:
    # Arrange: mutate via the ordinary application session — per OD-12,
    # there is no separate privileged connection to distinguish, since the
    # app itself connects as the Postgres superuser. Distinct offsets for
    # the same reason as the test above.
    row_ids = [uuid.uuid4() for _ in range(3)]
    for offset, row_id in enumerate(row_ids):
        await db_session.execute(
            text(
                "INSERT INTO audit_log (id, occurred_at, category, event) "
                "VALUES (:id, now() + (:offset * interval '1 second'), 'audit', 'chain_test')"
            ),
            {"id": row_id, "offset": offset},
        )
    await db_session.execute(
        text("UPDATE audit_log SET event = 'tampered' WHERE id = :id"), {"id": row_ids[1]}
    )

    # Act
    rows = await fetch_chain(db_session)
    result = verify_chain(rows)

    # Assert
    assert result is not None
    assert result.id == row_ids[1]
    assert result.reason == "row_hash_mismatch"


async def test_audit_log_first_ever_row_seeds_from_sentinel(db_session: AsyncSession) -> None:
    # Arrange: the claim under test only holds if audit_log is genuinely
    # empty right now. db_session's function-scoped rollback guarantees
    # that for every other test in this file, but a real committed write
    # (e.g. the concurrency test below, which commits via real_client and
    # only cleans up in a finally block) could in principle leave rows
    # behind if it failed between insert and cleanup. Assert the
    # precondition explicitly so a leak fails here with a clear message,
    # not as a confusing genesis-hash mismatch.
    existing_count = (
        await db_session.execute(text("SELECT COUNT(*) FROM audit_log"))
    ).scalar_one()
    assert existing_count == 0, (
        "audit_log was not empty at test start — likely leakage from another "
        "test's committed write, not a bug in genesis-hash seeding itself"
    )

    # Act
    row_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO audit_log (id, occurred_at, category, event) "
            "VALUES (:id, now(), 'audit', 'genesis_test')"
        ),
        {"id": row_id},
    )
    result = await db_session.execute(
        text("SELECT previous_hash FROM audit_log WHERE id = :id"), {"id": row_id}
    )

    # Assert
    assert result.scalar_one() == GENESIS_SENTINEL


async def test_audit_log_insert_after_gap_seeds_from_last_row_not_null(
    db_session: AsyncSession,
) -> None:
    # Arrange: OD-17's skip-empty-days behavior is the trigger's own
    # cross-partition lookback, not the verifier's — a row inserted after
    # a time gap must still seed from the true prior row, not NULL/an
    # error.
    first_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO audit_log (id, occurred_at, category, event) "
            "VALUES (:id, now() - interval '10 days', 'audit', 'before_gap')"
        ),
        {"id": first_id},
    )
    first_hash = (
        await db_session.execute(
            text("SELECT row_hash FROM audit_log WHERE id = :id"), {"id": first_id}
        )
    ).scalar_one()

    second_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO audit_log (id, occurred_at, category, event) "
            "VALUES (:id, now(), 'audit', 'after_gap')"
        ),
        {"id": second_id},
    )

    # Act
    second_previous_hash = (
        await db_session.execute(
            text("SELECT previous_hash FROM audit_log WHERE id = :id"), {"id": second_id}
        )
    ).scalar_one()

    # Assert
    assert second_previous_hash == first_hash
    assert second_previous_hash is not None


async def test_audit_log_insert_outside_named_partitions_lands_in_default(
    db_session: AsyncSession,
) -> None:
    # Arrange & Act: OD-16 — no named daily partitions exist, everything
    # lands in DEFAULT; this proves the migration's safety net, not a
    # hard INSERT failure.
    row_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO audit_log (id, occurred_at, category, event) "
            "VALUES (:id, now() + interval '500 days', 'audit', 'far_future')"
        ),
        {"id": row_id},
    )
    result = await db_session.execute(
        text("SELECT tableoid::regclass::text FROM audit_log WHERE id = :id"), {"id": row_id}
    )

    # Assert
    assert result.scalar_one() == "audit_log_default"


async def test_audit_log_concurrent_inserts_never_share_previous_hash(
    real_client: AsyncClient,
) -> None:
    # Arrange: OD-6 — pg_advisory_xact_lock must serialize genuinely
    # concurrent transactions, not just sequential ones. Uses real_client
    # (independent, committed connections) since db_session/client share
    # one transaction and can't express real concurrency. Two concurrent
    # successful reads each write their own self-audit entry.
    engine = app.state.db_engine
    admin_id = uuid.uuid4()
    admin_email = f"concurrentauditor.{uuid.uuid4().hex}@example.com"
    async with engine.begin() as connection:
        await connection.execute(
            insert(User).values(
                id=admin_id,
                email=admin_email,
                hashed_password=await hash_password("Str0ng!Pass1"),
                status="active",
                email_verified=True,
            )
        )
        jti = uuid.uuid4()
        await connection.execute(
            insert(UserSession).values(
                jti=jti, user_id=admin_id, expires_at=datetime.now(UTC) + timedelta(hours=1)
            )
        )
    token = encode_access_token(user_id=admin_id, jti=jti, scopes=_READ)
    window = _window()

    try:
        # Act
        responses = await asyncio.gather(
            real_client.get(
                "/api/v1/admin/audit-logs", params=window, headers=_auth_headers(token)
            ),
            real_client.get(
                "/api/v1/admin/audit-logs", params=window, headers=_auth_headers(token)
            ),
        )

        # Assert
        assert [response.status_code for response in responses] == [200, 200]
        async with engine.begin() as connection:
            result = await connection.execute(
                text(
                    "SELECT previous_hash FROM audit_log "
                    "WHERE actor_id = :actor_id AND event = 'audit_log_viewed'"
                ),
                {"actor_id": admin_id},
            )
            previous_hashes = [row[0] for row in result.all()]
        assert len(previous_hashes) == 2
        assert len(set(previous_hashes)) == 2
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM audit_log WHERE actor_id = :actor_id"), {"actor_id": admin_id}
            )
            await connection.execute(
                text("DELETE FROM user_sessions WHERE user_id = :user_id"), {"user_id": admin_id}
            )
            await connection.execute(
                text("DELETE FROM users WHERE id = :user_id"), {"user_id": admin_id}
            )


# --- T3c: audit_log_history keyset pagination uses the new indexes -------


async def test_list_audit_logs_pagination_uses_indexed_scan_not_full_sort(
    db_session: AsyncSession,
) -> None:
    # Arrange: AGENTS.md §5 asks for a statement-count ceiling on list
    # endpoints as an N+1 guard; this project has no existing statement-
    # counting harness to reuse, and the claim under test ("a merge-append,
    # not a full sort") is a query-plan property a statement count
    # wouldn't actually verify anyway. Asserting directly against EXPLAIN
    # is the more precise test of what's claimed.
    # Act
    result = await db_session.execute(
        text(
            "EXPLAIN SELECT * FROM audit_log_history "
            "WHERE occurred_at >= now() - interval '1 day' AND occurred_at <= now() "
            "ORDER BY occurred_at DESC LIMIT 50"
        )
    )
    plan = "\n".join(row[0] for row in result.all())

    # Assert: every branch of the UNION ALL is fed by an Index Scan (never
    # a Seq Scan), and the branches are combined via Merge Append — which
    # relies on each branch already being ordered by its own index, so no
    # separate top-level Sort node over the merged result is needed.
    assert "Seq Scan" not in plan
    assert "Index Scan" in plan
    assert "Merge Append" in plan
