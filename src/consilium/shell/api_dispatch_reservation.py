"""Fail-closed API reservation boundary; no trusted live observer exists yet."""

from __future__ import annotations

from typing import NoReturn

from consilium.adapters.api_http import AccessBlocked, HttpGrant
from consilium.adapters.api_plan import ApiPlan, ApiProfile, verify_plan
from consilium.core.contracts import AdapterRequest
from consilium.shell.api_dispatch_preflight import _inspect_current
from consilium.shell.storage import Conflict, SchemaError, SQLiteStore


def reserve_api_dispatch(
    store: SQLiteStore,
    plan: ApiPlan,
    request: AdapterRequest,
    grant: HttpGrant,
    profile: ApiProfile,
    *,
    expected_revision: int,
) -> NoReturn:
    """Recheck preparation under BEGIN IMMEDIATE, then reject live dispatch.

    The existing product has no registered trusted live observer. Consequently
    this boundary cannot create a reservation or SEND_STARTED event. A future
    successful reservation must validate genuine provenance and persist the
    exact plan and transition in this same transaction before returning a permit.
    Neither a preview nor a caller-supplied live flag can bypass this gate.
    """
    if type(expected_revision) is not int or expected_revision < 0:
        raise AccessBlocked("API_RESERVATION_REVISION_INVALID")
    if store._db.in_transaction:
        raise AccessBlocked("API_RESERVATION_REQUIRES_OWN_WRITE_TRANSACTION")
    reason = "API_RESERVATION_LEDGER_CONFLICT"
    try:
        with store._transaction():
            invalid = False
            try:
                request = AdapterRequest.model_validate(request)
                verify_plan(plan, request, grant, profile)
            except (ValueError, TypeError, AttributeError):
                invalid = True
            if invalid:
                reason = "API_RESERVATION_INPUT_INVALID"
            else:
                report = _inspect_current(store, plan, request, expected_revision)
                reason = "API_RESERVATION_" + report.gate
            # Raise within the transaction so rejected preparation rolls back.
            raise Conflict("API reservation rejected")
    except (Conflict, SchemaError, ValueError, TypeError):
        pass
    # Fixed public codes; private inputs and exceptions are not chained.
    raise AccessBlocked(reason)
