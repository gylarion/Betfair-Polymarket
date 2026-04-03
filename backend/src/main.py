from __future__ import annotations

import asyncio
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router, set_bot
from src.api.websocket import ws_manager
from src.clients.betfair_client import BetfairClient
from src.clients.polymarket_client import PolymarketClient
from src.config.settings import settings
from src.core.market_matcher import MarketMatcher
from src.core.opportunity_detector import OpportunityDetector
from src.core.price_monitor import PriceMonitor
from src.core.risk_manager import RiskManager
from src.core.trade_executor import TradeExecutor
from src.models.market import MatchedMarket
from src.storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class BotOrchestrator:
    """Main orchestrator that ties all components together."""

    def __init__(self):
        self.settings = settings
        self.db = Database()
        self.db.create_tables()

        self.betfair = BetfairClient()
        self.polymarket = PolymarketClient()
        self.matcher = MarketMatcher()
        self.detector = OpportunityDetector()
        self.risk = RiskManager()
        self.monitor = PriceMonitor(self.betfair, self.polymarket)
        self.executor = TradeExecutor(self.polymarket, self.risk, self.db)

        self.running = False
        self._tasks: list[asyncio.Task] = []

    async def initialize(self):
        logger.info(f"Initializing bot (demo_mode={settings.bot.demo_mode})")
        await self.betfair.connect()
        await self.polymarket.connect()

        bf_markets = await self.betfair.get_markets()
        pm_markets = await self.polymarket.get_markets()
        logger.info(f"Found {len(bf_markets)} Betfair markets, {len(pm_markets)} Polymarket markets")

        matched = self.matcher.match_markets(bf_markets, pm_markets)
        logger.info(f"Matched {len(matched)} market pairs")

        self.monitor.set_matched_markets(self.matcher.get_matched())
        self.monitor.on_price_update(self._on_price_update)

    def _on_price_update(self, mm: MatchedMarket):
        opportunities = self.detector.analyze(mm)
        for opp in opportunities:
            asyncio.create_task(self._handle_opportunity(opp, mm))

        asyncio.create_task(
            ws_manager.broadcast("market_update", {
                "id": mm.id,
                "event": mm.betfair.event_name,
                "betfair_selections": [
                    {"name": s.name, "price": s.back_price, "prob": s.implied_probability}
                    for s in mm.betfair.selections
                ],
                "polymarket_selections": [
                    {"name": s.name, "prob": s.implied_probability}
                    for s in mm.polymarket.selections
                ],
            })
        )

    async def _handle_opportunity(self, opp, mm: MatchedMarket):
        await ws_manager.broadcast("opportunity", opp.model_dump())
        trade = await self.executor.execute_opportunity(opp, mm)
        if trade:
            await ws_manager.broadcast("trade", trade.model_dump())

    async def run(self):
        self.running = True
        logger.info("Bot started")

        monitor_task = asyncio.create_task(self.monitor.start())
        exit_check_task = asyncio.create_task(self._exit_check_loop())
        self._tasks = [monitor_task, exit_check_task]

        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _exit_check_loop(self):
        while self.running:
            try:
                await self.executor.check_exits(self.matcher.get_matched())
            except Exception as e:
                logger.error(f"Exit check error: {e}")
            await asyncio.sleep(1.0)

    async def stop(self):
        self.running = False
        await self.monitor.stop()
        for task in self._tasks:
            task.cancel()
        await self.betfair.disconnect()
        await self.polymarket.disconnect()
        logger.info("Bot stopped")


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="Betfair-Polymarket Trading Bot",
        description="Automated cross-platform arbitrage trading bot",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    bot = BotOrchestrator()

    @app.on_event("startup")
    async def startup():
        set_bot(bot)
        await bot.initialize()
        asyncio.create_task(bot.run())

    @app.on_event("shutdown")
    async def shutdown():
        await bot.stop()

    return app


app = create_app()

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    uvicorn.run(
        "src.main:app",
        host=settings.server.api_host,
        port=settings.server.api_port,
        reload=False,
    )
