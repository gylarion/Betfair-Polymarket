from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.models.trade import TradeSide


class OpportunityStatus(str, Enum):
    DETECTED = "detected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: "")
    matched_market_id: str
    selection_name: str

    betfair_price: float  # Decimal odds
    betfair_implied_prob: float  # 0.0 - 1.0
    polymarket_price: float  # 0-100 cents

    edge_percent: float  # Difference as percentage
    suggested_side: TradeSide
    suggested_size_usdc: float

    status: OpportunityStatus = OpportunityStatus.DETECTED
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    expired_at: datetime | None = None
    trade_id: str | None = None
