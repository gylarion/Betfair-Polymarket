from __future__ import annotations

import asyncio
import json
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

GAMMA_URL = "https://gamma-api.polymarket.com"


def _parse_json_string(val: str | list | None) -> list:
    """Parse stringified JSON arrays from Gamma API (e.g. outcomePrices, clobTokenIds)."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


class PolymarketClient:
    """Wrapper around Polymarket Gamma API (public) and CLOB API (trading)."""

    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        if settings.bot.demo_mode:
            logger.info("Polymarket client running in DEMO mode")
            self._connected = True
            return True

        try:
            self._connected = True
            logger.info("Connected to Polymarket Gamma API (public read)")

            if settings.polymarket.private_key:
                from py_clob_client.client import ClobClient

                self._client = ClobClient(
                    settings.polymarket.clob_url,
                    key=settings.polymarket.private_key,
                    chain_id=settings.polymarket.chain_id,
                    funder=settings.polymarket.funder_address or None,
                )
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
                logger.info("Connected to Polymarket CLOB API (trading)")

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Polymarket: {e}")
            self._connected = True  # Gamma API still works without auth
            return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_markets(
        self,
        sport: SportType | None = None,
        tag_id: int | None = None,
    ) -> list[PlatformMarket]:
        if settings.bot.demo_mode:
            return self._generate_demo_markets(sport)

        try:
            import httpx

            params: dict = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": 50,
                "enableOrderBook": "true",
            }
            if tag_id:
                params["tag_id"] = tag_id

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{GAMMA_URL}/markets", params=params)
                resp.raise_for_status()
                data = resp.json()

            markets = []
            for item in data:
                # Parse stringified JSON arrays from Gamma API
                outcome_prices = _parse_json_string(item.get("outcomePrices"))
                clob_token_ids = _parse_json_string(item.get("clobTokenIds"))
                outcomes = _parse_json_string(item.get("outcome")) or ["Yes", "No"]

                if not clob_token_ids:
                    continue

                # Build selections from outcomes + prices + token IDs
                selections = []
                for i, token_id in enumerate(clob_token_ids):
                    name = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
                    price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.0
                    selections.append(
                        Selection(
                            id=str(token_id),
                            name=name,
                            back_price=None,
                            lay_price=None,
                            implied_probability=price,  # Already 0.0-1.0
                        )
                    )

                # Determine sport from event title or tags
                group_title = item.get("groupItemTitle") or ""
                question = item.get("question") or ""
                s = sport or SportType.FOOTBALL
                lower_text = (group_title + " " + question).lower()
                if any(w in lower_text for w in ["horse", "racing", "ascot", "cheltenham", "derby"]):
                    s = SportType.HORSE_RACING

                condition_id = item.get("conditionId") or str(item.get("id", ""))
                end_date = item.get("endDateIso") or item.get("endDate")
                start_time = None
                if end_date:
                    try:
                        start_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                markets.append(
                    PlatformMarket(
                        platform=Platform.POLYMARKET,
                        market_id=condition_id,
                        event_name=group_title or question,
                        market_name=question,
                        sport=s,
                        selections=selections,
                        start_time=start_time,
                        status=MarketStatus.OPEN if item.get("active") else MarketStatus.CLOSED,
                    )
                )

            logger.info(f"Fetched {len(markets)} markets from Polymarket Gamma API")
            return markets
        except Exception as e:
            logger.error(f"Error fetching Polymarket markets: {e}")
            return []

    async def get_market_by_id(self, market_id: int) -> dict | None:
        """Fetch a single market by its numeric ID."""
        if settings.bot.demo_mode:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{GAMMA_URL}/markets/{market_id}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None

    async def get_orderbook(self, token_id: str) -> dict:
        if settings.bot.demo_mode:
            return {"bids": [], "asks": []}

        if not self._client:
            return {"bids": [], "asks": []}
        book = await asyncio.to_thread(self._client.get_order_book, token_id)
        return book

    async def get_price(self, token_id: str) -> float | None:
        if settings.bot.demo_mode:
            import random
            return round(random.uniform(10, 90), 1)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.polymarket.clob_url}/price",
                    params={"token_id": token_id, "side": "buy"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("price", 0)) * 100  # Convert 0-1 to cents
            return None
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

        if not self._client:
            logger.error("CLOB client not initialized — need private key for trading")
            return None

        try:
            from py_clob_client.order_builder.constants import BUY, SELL

            order_side = BUY if side.lower() == "buy" else SELL
            order = await asyncio.to_thread(
                self._client.create_and_post_order,
                {
                    "tokenID": token_id,
                    "price": price / 100.0,  # Convert cents to 0-1
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
        if not self._client:
            return False
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
