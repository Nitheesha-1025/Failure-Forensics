"""User-scoped analytics (Phase 11)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..analytics.schemas import AnalyticsSummary
from ..analytics.service import AnalyticsService
from ..auth.deps import get_current_user, get_db
from ..db.models import User
from .trace_deps import trace_store

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalyticsSummary:
    store = trace_store(request)
    return AnalyticsService().summary_for_user(db, user=current_user, store=store)
