"""CSV / XLSX import connector (authorised files uploaded by admins or suppliers)."""
import csv
import io
from collections.abc import Iterable
from typing import Any

from app.services.market_data.base import ConnectorError, RawRecord, SourceConnector, register

# Accepted header aliases (uz / ru / en) -> canonical field
HEADER_ALIASES: dict[str, str] = {
    "product_name": "product_name", "product": "product_name", "mahsulot": "product_name", "товар": "product_name",
    "наименование": "product_name", "name": "product_name",
    "barcode": "barcode", "shtrix_kod": "barcode", "штрихкод": "barcode",
    "sku": "sku", "artikul": "sku", "артикул": "sku",
    "brand": "brand", "brend": "brand", "бренд": "brand",
    "category": "category", "kategoriya": "category", "категория": "category",
    "supplier": "supplier_name", "supplier_name": "supplier_name", "yetkazib_beruvchi": "supplier_name", "поставщик": "supplier_name",
    "supplier_tin": "supplier_tin", "stir": "supplier_tin", "инн": "supplier_tin",
    "supplier_type": "supplier_type",
    "price": "price", "narx": "price", "цена": "price",
    "currency": "currency", "valyuta": "currency", "валюта": "currency",
    "unit": "unit", "birlik": "unit", "ед": "unit", "единица": "unit",
    "region": "region", "viloyat": "region", "регион": "region", "область": "region",
    "price_type": "price_type", "narx_turi": "price_type", "тип_цены": "price_type",
    "observed_at": "observed_at", "date": "observed_at", "sana": "observed_at", "дата": "observed_at",
    "source_url": "source_url", "url": "source_url",
    "moq": "moq", "min_order": "moq", "мин_заказ": "moq",
    "available_qty": "available_qty", "stock": "available_qty", "qoldiq": "available_qty", "остаток": "available_qty",
    "delivery_available": "delivery_available", "delivery_cost": "delivery_cost",
    "valid_until": "valid_until",
    "record_type": "record_type",
}
MAX_ROWS = 20000


def _canon(h: str) -> str:
    key = (h or "").strip().lower().replace(" ", "_")
    return HEADER_ALIASES.get(key, key)


def parse_table(content: bytes, filename: str) -> list[RawRecord]:
    name = filename.lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="strict") if content else ""
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        rows = list(reader)
    elif name.endswith(".xlsx"):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [["" if v is None else v for v in r] for r in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raise ConnectorError("Only .csv and .xlsx files are supported")
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        raise ConnectorError("File is empty")
    if len(rows) - 1 > MAX_ROWS:
        raise ConnectorError(f"File has more than {MAX_ROWS} rows; split it")
    headers = [_canon(str(h)) for h in rows[0]]
    if "product_name" not in headers or "price" not in headers:
        raise ConnectorError("Required columns missing: product_name and price")
    out = []
    for r in rows[1:]:
        rec = {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
        out.append({k: (v.strip() if isinstance(v, str) else v) for k, v in rec.items()})
    return out


@register
class FileImportConnector(SourceConnector):
    type_key = "file_import"
    description = "CSV/XLSX price lists uploaded by authorised users. Columns: product_name, price, currency, unit, region, ..."
    config_schema = {"default_record_type": {"type": "string", "enum": ["observation", "offer"]},
                     "allow_create_products": {"type": "boolean"}}
    requires_terms_permission = False  # files are provided by authorised users

    def collect(self, content: bytes | None = None, filename: str = "", **_: Any) -> Iterable[RawRecord]:
        if content is None:
            raise ConnectorError("File import connector needs an uploaded file")
        return parse_table(content, filename)
