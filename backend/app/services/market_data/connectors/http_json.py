"""Generic connector for an *authorised* JSON API or official open-data feed.

No endpoints are built in: the admin supplies the URL and a field mapping for a source whose
terms have been reviewed and marked 'permitted'. It does not handle logins, CAPTCHAs or
anti-bot mechanisms and must not be used to bypass them."""
from collections.abc import Iterable
from typing import Any

import httpx

from app.services.market_data.base import ConnectorError, RawRecord, SourceConnector, register


def _dig(obj: Any, path: str) -> Any:
    for part in [p for p in path.split(".") if p]:
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit():
            obj = obj[int(part)]
        else:
            return None
    return obj


@register
class HttpJsonConnector(SourceConnector):
    type_key = "http_json"
    description = "Fetches JSON from an authorised URL and maps fields to TradeFlow records."
    config_schema = {
        "url": {"type": "string", "required": True},
        "records_path": {"type": "string", "help": "Dot path to the list of records, e.g. 'data.items'"},
        "field_map": {"type": "object", "help": "TradeFlow field -> dot path in each record"},
        "headers": {"type": "object", "help": "Static headers (e.g. API key header). Prefer env-provided secrets."},
        "static_fields": {"type": "object", "help": "Values applied to every record, e.g. {'region': 'UZ-TK'}"},
        "timeout_seconds": {"type": "number"},
    }
    requires_terms_permission = True

    def collect(self, client: httpx.Client | None = None, **_: Any) -> Iterable[RawRecord]:
        self.preflight()
        url = self.config.get("url")
        if not url or not str(url).startswith(("https://", "http://")):
            raise ConnectorError("Connector config needs a valid 'url'")
        fmap: dict = self.config.get("field_map") or {}
        if "product_name" not in fmap or "price" not in fmap:
            raise ConnectorError("field_map must map at least product_name and price")
        own = client is None
        client = client or httpx.Client(timeout=float(self.config.get("timeout_seconds", 30)),
                                        headers={"User-Agent": "TradeFlowBot/0.1 (+contact admin)"})
        try:
            resp = client.get(url, headers=self.config.get("headers") or {})
            if resp.status_code in (401, 403):
                raise ConnectorError(f"Source refused access (HTTP {resp.status_code}); not retrying or bypassing")
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as e:
            raise ConnectorError(f"HTTP error: {e}") from e
        finally:
            if own:
                client.close()
        records = _dig(payload, self.config.get("records_path", "")) if self.config.get("records_path") else payload
        if not isinstance(records, list):
            raise ConnectorError("records_path did not resolve to a list")
        static = self.config.get("static_fields") or {}
        out = []
        for r in records:
            rec = {k: _dig(r, v) for k, v in fmap.items()}
            rec.update({k: v for k, v in static.items() if rec.get(k) in (None, "")})
            rec.setdefault("source_url", url)
            out.append(rec)
        return out
