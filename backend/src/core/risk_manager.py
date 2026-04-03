from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.config.settings import settings
from src.models.opportunity import Opportunity
from src.models.trade import Trade

logger = logging.getLogger(__name__)


class RiskManager:
    """Enforces position limits, max daily loss, and other risk controls."""

    def __init__(self):
        self.max_position = settings.bot.max_position_usdc
        self.max_daily_loss = settings.bot.max_daily_loss_usdc
        self._open_positions: dict[str, float] = {}  # market_id -> USDC exposure
        self._daily_pnl: float = 0.0
        self._daily_reset: datetime = datetime.utcnow().replace(hour=0, minute=0, second=0)
        self._halted = False

    def check_opportunity(self, opp: Opportunity) -> tuple[bool, str]:
        """Check if an opportunity passes risk controls. Returns (allowed, reason)."""
        self._maybe_reset_daily()

        if self._halted:
            return False, "Trading halted due to daily loss limit"

        if self._daily_pnl <= -self.max_daily_loss:
            self._halted = True
            logger.warning(f"Daily loss limit reached: ${self._daily_pnl:.2f}")
            return False, f"Daily loss limit reached: ${self._daily_pnl:.2f}"

        current_exposure = self._open_positions.get(opp.matched_market_id, 0.0)
        if current_exposure + opp.suggested_size_usdc > self.max_position:
            allowed_size = self.max_position - current_exposure
            if allowed_size <= 1.0:
                return False, f"Max position reached for market {opp.matched_market_id}"
            opp.suggested_size_usdc = round(allowed_size, 2)

        total_exposure = sum(self._open_positions.values())
        if total_exposure > self.max_position * 5:
            return False, "Total portfolio exposure too high"

        return True, "OK"

    def record_entry(self, trade: Trade):
        mid = trade.matched_market_id
        self._open_positions[mid] = self._open_positions.get(mid, 0.0) + trade.entry_size_usdc

    def record_exit(self, trade: Trade):
        mid = trade.matched_market_id
        self._open_positions[mid] = max(0.0, self._open_positions.get(mid, 0.0) - trade.entry_size_usdc)
        if trade.pnl_usdc is not None:
            self._daily_pnl += trade.pnl_usdc

    def get_status(self) -> dict:
        return {
            "halted": self._halted,
            "daily_pnl": round(self._daily_pnl, 2),
            "max_daily_loss": self.max_daily_loss,
            "open_positions": dict(self._open_positions),
            "total_exposure": round(sum(self._open_positions.values()), 2),
        }

    def _maybe_reset_daily(self):
        now = datetime.utcnow()
        if now.date() > self._daily_reset.date():
            self._daily_pnl = 0.0
            self._daily_reset = now.replace(hour=0, minute=0, second=0)
            self._halted = False
            logger.info("Daily risk counters reset")
