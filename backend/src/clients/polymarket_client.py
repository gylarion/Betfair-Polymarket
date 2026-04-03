from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from src.config.settings import settings
from src.models.market import (
    MarketStatus,
    Platform,
    PlatformMarket,
    Selection,
    SportType,
)

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Wrapper around py-clob-client for Polymarket CLOB API."""

    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        if settings.bot.demo_mode:
            logger.info("Polymarket client running in DEMO mode")
            self._connected = True
            return True

        try:
            from py_clob_client.client import ClobClient

            self._client = ClobClient(
                settings.polymarket.clob_url,
                key=settings.polymarket.private_key,
                chain_id=settings.polymarket.chain_id,
                funder=settings.polymarket.funder_address or None,
            )
            creds = self._client.create_or_derive_api_creds()
            self._client.set_api_creds(creds)
            self._connected = True
            logger.info("Connected to Polymarket CLOB API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Polymarket: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_markets(
        self,
        sport: SportType | None = None,
        tag: str | None = None,
    ) -> list[PlatformMarket]:
        if settings.bot.demo_mode:
            return self._generate_demo_markets(sport)

        try:
            import httpx

            params: dict = {"active": "true", "closed": "false", "limit": 50}
            if tag:
                params["tag"] = tag
            elif sport == SportType.FOOTBALL:
                params["tag"] = "soccer"
            elif sport == SportType.HORSE_RACING:
                params["tag"] = "horse-racing"
            else:
                params["tag"] = "sports"

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.polymarket.gamma_url}/markets", params=params)
                resp.raise_for_status()
                data = resp.json()

            markets = []
            for item in data:
                tokens = item.get("tokens", [])
                selections = []
                for tok in tokens:
                    outcome = tok.get("outcome", "Unknown")
                    price = tok.get("price", 0)
                    selections.append(
                        Selection(
                            id=tok.get("token_id", ""),
                            name=outcome,
                            back_price=None,
                            lay_price=None,
                            implied_probability=price / 100.0 if price > 1 else price,
                        )
                    )

                s = SportType.FOOTBALL
                if sport:
                    s = sport
                elif "horse" in (item.get("groupItemTitle") or "").lower():
                    s = SportType.HORSE_RACING

                markets.append(
                    PlatformMarket(
                        platform=Platform.POLYMARKET,
                        market_id=item.get("conditionId", item.get("id", "")),
                        event_name=item.get("groupItemTitle", item.get("question", "")),
                        market_name=item.get("question", ""),
                        sport=s,
                        selections=selections,
                        start_time=None,
                        status=MarketStatus.OPEN,
                    )
                )
            return markets
        except Exception as e:
            logger.error(f"Error fetching Polymarket markets: {e}")
            return []

    async def get_orderbook(self, token_id: str) -> dict:
        if settings.bot.demo_mode:
            return {"bids": [], "asks": []}

        book = await asyncio.to_thread(self._client.get_order_book, token_id)
        return book

    async def get_price(self, token_id: str) -> float | None:
        if settings.bot.demo_mode:
            import random
            return round(random.uniform(10, 90), 1)

        try:
            resp = await asyncio.to_thread(self._client.get_price, token_id)
            return float(resp.get("price", 0))
        except Exception as e:
            logger.error(f"Error getting price for {token_id}: {e}")
            return None

    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
    ) -> dict | None:
        if settings.bot.demo_mode:
            import uuid
            logger.info(f"DEMO: Placing {side} order for {token_id} at {price}¢, size ${size}")
            return {"orderID": str(uuid.uuid4()), "status": "MATCHED"}

        try:
            from py_clob_client.order_builder.constants import BUY, SELL

            order_side = BUY if side.lower() == "buy" else SELL
            order = await asyncio.to_thread(
                self._client.create_and_post_order,
                {
                    "tokenID": token_id,
                    "price": price / 100.0,
                    "size": size,
                    "side": order_side,
                },
            )
            return order
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        if settings.bot.demo_mode:
            return True

        try:
            await asyncio.to_thread(self._client.cancel, order_id)
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def disconnect(self):
        self._connected = False

    # ── Demo mode helpers ──

    def _generate_demo_markets(self, sport: SportType | None = None) -> list[PlatformMarket]:
        import random

        demo_football = [
            ("Manchester United vs Chelsea", "Will Manchester United win?", ["Yes", "No"]),
            ("Liverpool vs Arsenal", "Will Liverpool win?", ["Yes", "No"]),
            ("Man City vs Tottenham", "Will Man City win?", ["Yes", "No"]),
            ("Newcastle vs Everton", "Will Newcastle win?", ["Yes", "No"]),
        ]
        demo_racing = [
            ("14:30 Ascot - Royal Stakes", "Will Golden Thunder win Royal Stakes?", ["Yes", "No"]),
            ("15:00 Cheltenham - Champion Hurdle", "Will Storm Chaser win Champion Hurdle?", ["Yes", "No"]),
            ("15:30 Leopardstown - Irish Gold Cup", "Will Celtic Warrior win Irish Gold Cup?", ["Yes", "No"]),
        ]

        markets = []
        now = datetime.utcnow()

        if sport != SportType.HORSE_RACING:
            for i, (event, question, outcomes) in enumerate(demo_football):
                yes_prob = round(random.uniform(0.15, 0.70), 3)
                selections = [
                    Selection(
                        id=f"pm_fb_{i}_yes",
                        name="Yes",
                        implied_probability=yes_prob,
                    ),
                    Selection(
                        id=f"pm_fb_{i}_no",
                        name="No",
                        implied_probability=round(1.0 - yes_prob, 3),
                    ),
                ]
                markets.append(
                    PlatformMarket(
                        platform=Platform.POLYMARKET,
                        market_id=f"pm_football_{i}",
                        event_name=event,
                        market_name=question,
                        sport=SportType.FOOTBALL,
                        selections=selections,
                        start_time=now + timedelta(hours=random.randint(1, 24)),
                    )
                )

        if sport != SportType.FOOTBALL:
            for i, (event, question, outcomes) in enumerate(demo_racing):
                yes_prob = round(random.uniform(0.10, 0.50), 3)
                selections = [
                    Selection(
                        id=f"pm_hr_{i}_yes",
                        name="Yes",
                        implied_probability=yes_prob,
                    ),
                    Selection(
                        id=f"pm_hr_{i}_no",
                        name="No",
                        implied_probability=round(1.0 - yes_prob, 3),
                    ),
                ]
                markets.append(
                    PlatformMarket(
                        platform=Platform.POLYMARKET,
                        market_id=f"pm_racing_{i}",
                        event_name=event,
                        market_name=question,
                        sport=SportType.HORSE_RACING,
                        selections=selections,
                        start_time=now + timedelta(hours=random.randint(1, 12)),
                    )
                )
        return markets
