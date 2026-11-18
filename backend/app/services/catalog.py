"""Dynamic attribute validation driven by category definitions stored in the DB."""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CategoryAttribute, Product, ProductAttributeValue


def validate_and_apply_attributes(db: Session, product: Product, values: list[dict[str, Any]], partial: bool = False) -> None:
    defs = {a.id: a for a in db.scalars(select(CategoryAttribute).where(CategoryAttribute.category_id == product.category_id)).all()}
    given = {int(v["attribute_id"]): v.get("value") for v in values}
    errors: list[str] = []
    for aid in given:
        if aid not in defs:
            errors.append(f"Attribute {aid} does not belong to this product's category")
    if not partial:
        for a in defs.values():
            if a.is_required and (given.get(a.id) in (None, "", [])):
                errors.append(f"Attribute '{a.code}' is required")
    if errors:
        raise HTTPException(422, errors)

    existing = {v.attribute_id: v for v in product.attribute_values}
    for aid, raw in given.items():
        a = defs[aid]
        pav = existing.get(aid) or ProductAttributeValue(attribute_id=aid)
        pav.value_text = pav.value_number = pav.value_bool = pav.value_json = None
        if raw in (None, "", []):
            if aid in existing:
                product.attribute_values.remove(existing[aid])
            continue
        try:
            if a.data_type == "number":
                pav.value_number = Decimal(str(raw))
            elif a.data_type == "boolean":
                if not isinstance(raw, bool):
                    raise ValueError
                pav.value_bool = raw
            elif a.data_type == "date":
                pav.value_json = date.fromisoformat(str(raw)).isoformat()
            elif a.data_type == "select":
                allowed = {o.value for o in a.options}
                if str(raw) not in allowed:
                    raise ValueError
                pav.value_text = str(raw)
            elif a.data_type == "multiselect":
                allowed = {o.value for o in a.options}
                vals = [str(x) for x in (raw if isinstance(raw, list) else [raw])]
                if any(v not in allowed for v in vals):
                    raise ValueError
                pav.value_json = vals
            else:
                s = str(raw).strip()
                if len(s) > 2000:
                    raise ValueError
                pav.value_text = s
        except (ValueError, InvalidOperation):
            raise HTTPException(422, f"Invalid value for attribute '{a.code}' ({a.data_type})")
        if aid not in existing:
            product.attribute_values.append(pav)
