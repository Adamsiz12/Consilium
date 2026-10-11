"""Read-only API/ledger correlation; a report is never a dispatch permit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from consilium.adapters.api_http import AccessBlocked, HttpGrant
from consilium.adapters.api_plan import ApiPlan, ApiProfile, verify_plan
from consilium.core.contracts import AdapterRequest, ConnectionSpec
from consilium.core.operation_states import AttemptState
from consilium.shell.storage import Conflict, SchemaError, SQLiteStore


@dataclass(frozen=True)
class ApiDispatchPreflight:
    attempt_id: UUID
    ledger_revision: int
    operation_hash: str
    gate: Literal["CONTEXT_ADMISSION_REQUIRED", "LIVE_OBSERVER_NOT_REGISTERED"]
    dispatch_allowed: Literal[False] = field(default=False, init=False)
    scope: str = field(default="READ_ONLY_API_LEDGER_CHECK_NOT_DISPATCH_PERMISSION", init=False)


def inspect_api_dispatch(
    store: SQLiteStore,
    plan: ApiPlan,
    request: AdapterRequest,
    grant: HttpGrant,
    profile: ApiProfile,
    *,
    expected_revision: int,
) -> ApiDispatchPreflight:
    """Verify exact preparation against one committed SQLite read snapshot.

    No live observer is registered in the product. Even a valid local admission
    leaves dispatch blocked. Future reservation must recheck these conditions
    atomically; this historical preview cannot be consumed as an authorization.
    """
    if type(expected_revision) is not int or expected_revision < 0:
        raise AccessBlocked("API_PREFLIGHT_REVISION_INVALID")
    invalid = False
    try:
        request = AdapterRequest.model_validate(request)
        verify_plan(plan, request, grant, profile)
    except (ValueError, TypeError, AttributeError):
        invalid = True
    if invalid:
        raise AccessBlocked("API_PREFLIGHT_INPUT_INVALID")
    if store._db.in_transaction:
        raise AccessBlocked("API_PREFLIGHT_REQUIRES_OWN_READ_SNAPSHOT")
    inconsistent = False
    try:
        with store._transaction(write=False):
            record = store.ledger.get_attempt(request.intent.identity.attempt_id)
            store.ledger._current(record, expected_revision, active=False)
            binding = store._db.execute(
                "SELECT spec_json FROM bindings WHERE debate_id=? AND participant_id=?",
                (str(record.intent.debate_id), str(record.intent.participant_id)),
            ).fetchone()
            if (record.intent != request.intent or binding is None
                    or ConnectionSpec.model_validate_json(binding[0]) != request.connection
                    or record.state != AttemptState.PREPARED):
                raise Conflict("Prepared API operation does not match current storage")
            wait = store._db.execute(
                "SELECT wait_state FROM debates WHERE debate_id=?",
                (str(record.intent.debate_id),),
            ).fetchone()[0]
            if wait != "ACTIVE" or store.ledger._has_outstanding(record.intent.debate_id):
                raise Conflict("API dispatch is blocked by current ledger gates")
            bundle = store.admissions.get(record.intent.identity.logical_operation_id)
            gate: Literal["CONTEXT_ADMISSION_REQUIRED", "LIVE_OBSERVER_NOT_REGISTERED"] = (
                "CONTEXT_ADMISSION_REQUIRED"
            )
            if bundle is not None:
                store.admissions.require_current(
                    request.intent.identity.attempt_id, expected_revision=expected_revision
                )
                gate = "LIVE_OBSERVER_NOT_REGISTERED"
            report = ApiDispatchPreflight(
                attempt_id=request.intent.identity.attempt_id,
                ledger_revision=expected_revision,
                operation_hash=plan.operation_hash,
                gate=gate,
            )
    except (Conflict, SchemaError, ValueError, TypeError):
        inconsistent = True
    if inconsistent:
        raise AccessBlocked("API_PREFLIGHT_LEDGER_CONFLICT")
    return report
