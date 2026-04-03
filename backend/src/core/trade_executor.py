from __future__ import annotations

import logging
import uuid
from datetime import datetime

from src.clients.polymarket_client import PolymarketClient
from src.core.risk_manager import RiskManager
from src.models.market import MatchedMarket
from src.models.opportunity import Opportunity, OpportunityStatus
from src.models.trade import Trade, TradeStatus, TradeSide
from src.storage.database import Database

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Executes trades on Polymarket based on detected opportunities."""

    def __init__(
        self,
        polymarket: PolymarketClient,
        risk_manager: RiskManager,
        db: Database,
    ):
        self.polymarket = polymarket
        self.risk = risk_manager
        self.db = db
        self._active_trades: dict[str, Trade] = {}

    async def execute_opportunity(
        self,
        opp: Opportunity,
        matched_market: MatchedMarket,
    ) -> Trade | None:
        """Execute a trade based on detected opportunity."""
        allowed, reason = self.risk.check_opportunity(opp)
        if not allowed:
            logger.info(f"Opportunity rejected by risk manager: {reason}")
            opp.status = OpportunityStatus.SKIPPED
            return None

        pm_sel_id = matched_market.selection_mapping.get(
            next(
                (bf_id for bf_id, pm_id in matched_market.selection_mapping.items()),
                "",
            )
        )
        if not pm_sel_id:
            logger.error("No Polymarket selection ID found for opportunity")
            return None

        trade = Trade(
            id=str(uuid.uuid4())[:8],
            matched_market_id=matched_market.id,
            selection_name=opp.selection_name,
            entry_side=opp.suggested_side,
            entry_price=opp.polymarket_price,
            entry_size_usdc=opp.suggested_size_usdc,
            betfair_price_at_entry=opp.betfair_price,
            polymarket_price_at_entry=opp.polymarket_price,
            edge_percent=opp.edge_percent,
        )

        result = await self.polymarket.place_order(
            token_id=pm_sel_id,
            side=opp.suggested_side.value,
            price=opp.polymarket_price,
            size=opp.suggested_size_usdc,
        )

        if result:
            trade.entry_order_id = result.get("orderID")
            trade.entry_time = datetime.utcnow()
            trade.status = TradeStatus.ENTRY_FILLED
            trade.entry_filled_price = opp.polymarket_price
            self.risk.record_entry(trade)
            opp.status = OpportunityStatus.EXECUTED
            opp.trade_id = trade.id
            self._active_trades[trade.id] = trade
            self.db.save_trade(trade)
            logger.info(
                f"Trade executed: {trade.selection_name} "
                f"| {trade.entry_side.value} at {trade.entry_price}¢ "
                f"| size ${trade.entry_size_usdc}"
            )
            return trade
        else:
            trade.status = TradeStatus.FAILED
            opp.status = OpportunityStatus.SKIPPED
            self.db.save_trade(trade)
            logger.error(f"Failed to execute trade for {opp.selection_name}")
            return None

    async def check_exits(self, matched_markets: dict[str, MatchedMarket]):
        """Check active trades for exit conditions."""
        for trade_id, trade in list(self._active_trades.items()):
            if trade.status != TradeStatus.ENTRY_FILLED:
                continue

            mm = matched_markets.get(trade.matched_market_id)
            if not mm:
                continue

            pm_sel = next(
                (s for s in mm.polymarket.selections
                 if s.id in mm.selection_mapping.values()),
                None,
            )
            if not pm_sel or pm_sel.implied_probability is None:
                continue

            current_price = pm_sel.implied_probability * 100
            entry_price = trade.entry_filled_price or trade.entry_price

            should_exit = False
            if trade.entry_side == TradeSide.BUY:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                should_exit = profit_pct >= 1.0 or profit_pct <= -2.0
            else:
                profit_pct = ((entry_price - current_price) / entry_price) * 100
                should_exit = profit_pct >= 1.0 or profit_pct <= -2.0

            if should_exit:
                await self._exit_trade(trade, current_price, mm)

    async def _exit_trade(self, trade: Trade, exit_price: float, mm: MatchedMarket):
        pm_sel_id = next(
            (pm_id for pm_id in mm.selection_mapping.values()),
            None,
        )
        if not pm_sel_id:
            return

        exit_side = "sell" if trade.entry_side == TradeSide.BUY else "buy"
        result = await self.polymarket.place_order(
            token_id=pm_sel_id,
            side=exit_side,
            price=exit_price,
            size=trade.entry_size_usdc,
        )

        if result:
            trade.exit_order_id = result.get("orderID")
            trade.exit_price = exit_price
            trade.exit_filled_price = exit_price
            trade.exit_time = datetime.utcnow()
            trade.status = TradeStatus.COMPLETED

            entry = trade.entry_filled_price or trade.entry_price
            if trade.entry_side == TradeSide.BUY:
                trade.pnl_usdc = round(
                    (exit_price - entry) / 100.0 * trade.entry_size_usdc, 4
                )
            else:
                trade.pnl_usdc = round(
                    (entry - exit_price) / 100.0 * trade.entry_size_usdc, 4
                )

            self.risk.record_exit(trade)
            self.db.save_trade(trade)
            del self._active_trades[trade.id]

            logger.info(
                f"Trade exited: {trade.selection_name} "
                f"| P/L: ${trade.pnl_usdc:.4f} "
                f"| entry={entry}¢ exit={exit_price}¢"
            )

    def get_active_trades(self) -> list[Trade]:
        return list(self._active_trades.values())
