from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from src.clients.betfair_client import BetfairClient
from src.clients.polymarket_client import PolymarketClient
from src.config.settings import settings
from src.models.market import MatchedMarket

logger = logging.getLogger(__name__)

PriceCallback = Callable[[MatchedMarket], None]


class PriceMonitor:
    """Continuously polls both platforms and updates matched market prices."""

    def __init__(
        self,
        betfair: BetfairClient,
        polymarket: PolymarketClient,
    ):
        self.betfair = betfair
        self.polymarket = polymarket
        self._running = False
        self._callbacks: list[PriceCallback] = []
        self._matched_markets: dict[str, MatchedMarket] = {}

    def on_price_update(self, callback: PriceCallback):
        self._callbacks.append(callback)

    def set_matched_markets(self, markets: dict[str, MatchedMarket]):
        self._matched_markets = markets

    async def start(self):
        self._running = True
        logger.info("Price monitor started")
        interval = settings.bot.poll_interval_ms / 1000.0

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                logger.error(f"Price monitor error: {e}")
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False
        logger.info("Price monitor stopped")

    async def _poll_cycle(self):
        if not self._matched_markets:
            return

        bf_ids = [m.betfair.market_id for m in self._matched_markets.values()]
        bf_prices = await self.betfair.get_market_prices(bf_ids)

        for mid, mm in list(self._matched_markets.items()):
            bf_sels = bf_prices.get(mm.betfair.market_id, [])
            if bf_sels:
                mm.betfair.selections = bf_sels
                mm.betfair.last_updated = datetime.utcnow()

            for pm_sel in mm.polymarket.selections:
                price = await self.polymarket.get_price(pm_sel.id)
                if price is not None:
                    pm_sel.implied_probability = price / 100.0
            mm.polymarket.last_updated = datetime.utcnow()

            for cb in self._callbacks:
                try:
                    cb(mm)
                except Exception as e:
                    logger.error(f"Price callback error: {e}")
