from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_optional_user
from app.core.ratelimit import assistant_rate_limit
from app.models import SearchEvent, User
from app.schemas import AssistantIn
from app.services.assistant.engine import answer
from app.services.assistant.llm import get_provider

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status")
def status():
    p = get_provider()
    s = get_settings()
    return {"llm_configured": p is not None, "provider": p.name if p else None, "model": s.llm_model if p else None,
            "fallback": "deterministic"}


@router.post("/ask", dependencies=[Depends(assistant_rate_limit)])
def ask(body: AssistantIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    res = answer(db, body.question, include_simulated=body.include_simulated, language=body.language)
    prod = res["entities"]["product"]
    db.add(SearchEvent(query=f"ai:{body.question[:290]}", product_id=prod["id"] if prod else None,
                       user_id=user.id if user else None))
    db.commit()
    return res
