from __future__ import annotations

import logging
import uuid
from datetime import datetime

from src.config.settings import settings
from src.models.market import MatchedMarket
from src.models.opportunity import Opportunity, OpportunityStatus
from src.models.trade import TradeSide

logger = logging.getLogger(__name__)


class OpportunityDetector:
    """Detects price discrepancies between Betfair and Polymarket."""

    def __init__(self, min_edge: float | None = None):
        self.min_edge = min_edge or settings.bot.min_edge_percent
        self._opportunities: list[Opportunity] = []
        self._max_history = 200

    def analyze(self, matched_market: MatchedMarket) -> list[Opportunity]:
        """Analyze a matched market for trading opportunities."""
        opportunities = []

        for bf_sel_id, pm_sel_id in matched_market.selection_mapping.items():
            bf_sel = next(
                (s for s in matched_market.betfair.selections if s.id == bf_sel_id),
                None,
            )
            pm_sel = next(
                (s for s in matched_market.polymarket.selections if s.id == pm_sel_id),
                None,
            )
            if not bf_sel or not pm_sel:
                continue
            if bf_sel.back_price is None or pm_sel.implied_probability is None:
                continue

            bf_implied = 1.0 / bf_sel.back_price  # Betfair implied probability
            pm_price_cents = pm_sel.implied_probability * 100  # Polymarket price in cents

            # Edge: difference between Betfair implied prob and Polymarket price
            # If Betfair says higher probability than Polymarket → BUY on Polymarket
            # If Betfair says lower probability than Polymarket → SELL on Polymarket
            edge = (bf_implied * 100) - pm_price_cents
            edge_percent = abs(edge)

            if edge_percent < self.min_edge:
                continue

            side = TradeSide.BUY if edge > 0 else TradeSide.SELL
            size = min(
                settings.bot.max_position_usdc,
                settings.bot.max_position_usdc * (edge_percent / 10.0),
            )

            opp = Opportunity(
                id=str(uuid.uuid4())[:8],
                matched_market_id=matched_market.id,
                selection_name=bf_sel.name,
                betfair_price=bf_sel.back_price,
                betfair_implied_prob=round(bf_implied, 4),
                polymarket_price=round(pm_price_cents, 2),
                edge_percent=round(edge_percent, 2),
                suggested_side=side,
                suggested_size_usdc=round(size, 2),
            )
            opportunities.append(opp)

            self._opportunities.append(opp)
            if len(self._opportunities) > self._max_history:
                self._opportunities = self._opportunities[-self._max_history:]

            logger.info(
                f"Opportunity: {bf_sel.name} | edge={edge_percent:.2f}% "
                f"| BF={bf_sel.back_price} ({bf_implied:.3f}) "
                f"| PM={pm_price_cents:.1f}¢ | {side.value.upper()}"
            )

        return opportunities

    def get_recent(self, limit: int = 50) -> list[Opportunity]:
        return list(reversed(self._opportunities[-limit:]))
