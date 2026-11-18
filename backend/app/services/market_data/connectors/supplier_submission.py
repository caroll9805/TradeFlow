"""Supplier submissions arrive through the Offers API (push model), not by polling.
This connector exists so the source appears in the registry with health metrics."""
from collections.abc import Iterable
from typing import Any

from app.services.market_data.base import RawRecord, SourceConnector, register


@register
class SupplierSubmissionConnector(SourceConnector):
    type_key = "supplier_submission"
    description = "Offers published by registered suppliers through the TradeFlow supplier dashboard/API."
    requires_terms_permission = False

    def collect(self, **_: Any) -> Iterable[RawRecord]:
        return []


@register
class ManualEntryConnector(SourceConnector):
    type_key = "manual_entry"
    description = "Observations entered by market data administrators (e.g. from official bulletins)."
    requires_terms_permission = False

    def collect(self, records: list[RawRecord] | None = None, **_: Any) -> Iterable[RawRecord]:
        return records or []
