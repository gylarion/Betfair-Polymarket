from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TradeStatus(str, Enum):
    PENDING = "pending"
    ENTRY_PLACED = "entry_placed"
    ENTRY_FILLED = "entry_filled"
    EXIT_PLACED = "exit_placed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Trade(BaseModel):
    id: str = Field(default_factory=lambda: "")
    matched_market_id: str
    selection_name: str

    entry_side: TradeSide
    entry_price: float  # Polymarket price 0-100
    entry_size_usdc: float
    entry_order_id: str | None = None
    entry_filled_price: float | None = None
    entry_time: datetime | None = None

    exit_price: float | None = None
    exit_order_id: str | None = None
    exit_filled_price: float | None = None
    exit_time: datetime | None = None

    betfair_price_at_entry: float  # Decimal odds from Betfair at time of entry
    polymarket_price_at_entry: float  # Polymarket price at time of entry
    edge_percent: float  # Detected edge at entry

    status: TradeStatus = TradeStatus.PENDING
    pnl_usdc: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeSummary(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_usdc: float = 0.0
    avg_edge_percent: float = 0.0
    largest_win_usdc: float = 0.0
    largest_loss_usdc: float = 0.0
    win_rate: float = 0.0
