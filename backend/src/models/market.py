from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SportType(str, Enum):
    FOOTBALL = "football"
    HORSE_RACING = "horse_racing"


class Platform(str, Enum):
    BETFAIR = "betfair"
    POLYMARKET = "polymarket"


class MarketStatus(str, Enum):
    OPEN = "open"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Selection(BaseModel):
    """A single outcome within a market (e.g. 'Liverpool to win')."""
    id: str
    name: str
    back_price: float | None = None  # Best available back price (decimal odds on Betfair)
    lay_price: float | None = None
    implied_probability: float | None = None  # 0.0 - 1.0


class PlatformMarket(BaseModel):
    """Market data from a single platform."""
    platform: Platform
    market_id: str
    event_name: str
    market_name: str
    sport: SportType
    selections: list[Selection] = Field(default_factory=list)
    start_time: datetime | None = None
    status: MarketStatus = MarketStatus.OPEN
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MatchedMarket(BaseModel):
    """A pair of markets from Betfair and Polymarket that represent the same event."""
    id: str
    betfair: PlatformMarket
    polymarket: PlatformMarket
    match_confidence: float = 0.0  # 0.0 - 1.0
    selection_mapping: dict[str, str] = Field(default_factory=dict)  # betfair_sel_id -> poly_sel_id
