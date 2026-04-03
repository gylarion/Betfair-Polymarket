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

# Betfair event type IDs
FOOTBALL_EVENT_TYPE = "1"
HORSE_RACING_EVENT_TYPE = "7"

SPORT_MAP = {
    FOOTBALL_EVENT_TYPE: SportType.FOOTBALL,
    HORSE_RACING_EVENT_TYPE: SportType.HORSE_RACING,
}


class BetfairClient:
    """Wrapper around betfairlightweight for Betfair Exchange API."""

    def __init__(self):
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        if settings.bot.demo_mode:
            logger.info("Betfair client running in DEMO mode")
            self._connected = True
            return True

        try:
            import betfairlightweight

            self._client = betfairlightweight.APIClient(
                username=settings.betfair.username,
                password=settings.betfair.password,
                app_key=settings.betfair.app_key,
                certs=settings.betfair.cert_path,
            )
            await asyncio.to_thread(self._client.login)
            self._connected = True
            logger.info("Connected to Betfair Exchange API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Betfair: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_markets(
        self,
        sport: SportType | None = None,
        hours_ahead: int = 24,
    ) -> list[PlatformMarket]:
        if settings.bot.demo_mode:
            return self._generate_demo_markets(sport)

        event_type_ids = []
        if sport == SportType.FOOTBALL:
            event_type_ids = [FOOTBALL_EVENT_TYPE]
        elif sport == SportType.HORSE_RACING:
            event_type_ids = [HORSE_RACING_EVENT_TYPE]
        else:
            event_type_ids = [FOOTBALL_EVENT_TYPE, HORSE_RACING_EVENT_TYPE]

        markets = []
        for event_type_id in event_type_ids:
            raw = await self._fetch_markets(event_type_id, hours_ahead)
            markets.extend(raw)
        return markets

    async def _fetch_markets(self, event_type_id: str, hours_ahead: int) -> list[PlatformMarket]:
        import betfairlightweight.filters as filters

        now = datetime.utcnow()
        market_filter = filters.market_filter(
            event_type_ids=[event_type_id],
            market_countries=["GB", "IE"] if event_type_id == HORSE_RACING_EVENT_TYPE else ["GB"],
            market_type_codes=["WIN"] if event_type_id == HORSE_RACING_EVENT_TYPE else ["MATCH_ODDS"],
            market_start_time={
                "from": now.isoformat(),
                "to": (now + timedelta(hours=hours_ahead)).isoformat(),
            },
        )

        catalogues = await asyncio.to_thread(
            self._client.betting.list_market_catalogue,
            filter=market_filter,
            market_projection=["RUNNER_DESCRIPTION", "EVENT", "MARKET_START_TIME"],
            max_results=50,
            sort="FIRST_TO_START",
        )

        if not catalogues:
            return []

        market_ids = [c.market_id for c in catalogues]
        books = await asyncio.to_thread(
            self._client.betting.list_market_book,
            market_ids=market_ids,
            price_projection={"priceData": ["EX_BEST_OFFERS"]},
        )
        book_map = {b.market_id: b for b in books}

        result = []
        for cat in catalogues:
            book = book_map.get(cat.market_id)
            selections = []
            if book:
                for runner in book.runners:
                    cat_runner = next(
                        (r for r in cat.runners if r.selection_id == runner.selection_id),
                        None,
                    )
                    back = runner.ex.available_to_back[0].price if runner.ex.available_to_back else None
                    lay = runner.ex.available_to_lay[0].price if runner.ex.available_to_lay else None
                    selections.append(
                        Selection(
                            id=str(runner.selection_id),
                            name=cat_runner.runner_name if cat_runner else str(runner.selection_id),
                            back_price=back,
                            lay_price=lay,
                            implied_probability=1.0 / back if back else None,
                        )
                    )

            status = MarketStatus.OPEN
            if book and book.status == "CLOSED":
                status = MarketStatus.CLOSED
            elif book and book.status == "SUSPENDED":
                status = MarketStatus.SUSPENDED

            result.append(
                PlatformMarket(
                    platform=Platform.BETFAIR,
                    market_id=cat.market_id,
                    event_name=cat.event.name if cat.event else cat.market_name,
                    market_name=cat.market_name,
                    sport=SPORT_MAP.get(event_type_id, SportType.FOOTBALL),
                    selections=selections,
                    start_time=cat.market_start_time,
                    status=status,
                )
            )
        return result

    async def get_market_prices(self, market_ids: list[str]) -> dict[str, list[Selection]]:
        if settings.bot.demo_mode:
            return self._demo_prices(market_ids)

        books = await asyncio.to_thread(
            self._client.betting.list_market_book,
            market_ids=market_ids,
            price_projection={"priceData": ["EX_BEST_OFFERS"]},
        )

        result = {}
        for book in books:
            selections = []
            for runner in book.runners:
                back = runner.ex.available_to_back[0].price if runner.ex.available_to_back else None
                lay = runner.ex.available_to_lay[0].price if runner.ex.available_to_lay else None
                selections.append(
                    Selection(
                        id=str(runner.selection_id),
                        name=str(runner.selection_id),
                        back_price=back,
                        lay_price=lay,
                        implied_probability=1.0 / back if back else None,
                    )
                )
            result[book.market_id] = selections
        return result

    async def disconnect(self):
        if self._client and not settings.bot.demo_mode:
            try:
                await asyncio.to_thread(self._client.logout)
            except Exception:
                pass
        self._connected = False

    # ── Demo mode helpers ──

    def _generate_demo_markets(self, sport: SportType | None = None) -> list[PlatformMarket]:
        import random

        demo_football = [
            ("Manchester United vs Chelsea", ["Man Utd", "Draw", "Chelsea"]),
            ("Liverpool vs Arsenal", ["Liverpool", "Draw", "Arsenal"]),
            ("Man City vs Tottenham", ["Man City", "Draw", "Tottenham"]),
            ("Newcastle vs Everton", ["Newcastle", "Draw", "Everton"]),
        ]
        demo_racing = [
            ("14:30 Ascot - Royal Stakes", ["Golden Thunder", "Silver Arrow", "Dark Prince", "Swift Runner"]),
            ("15:00 Cheltenham - Champion Hurdle", ["Storm Chaser", "Iron Will", "Lucky Star"]),
            ("15:30 Leopardstown - Irish Gold Cup", ["Celtic Warrior", "Mountain King", "Green Flash"]),
        ]

        markets = []
        now = datetime.utcnow()

        if sport != SportType.HORSE_RACING:
            for i, (name, sels) in enumerate(demo_football):
                selections = []
                for j, sel_name in enumerate(sels):
                    price = round(random.uniform(1.5, 8.0), 2)
                    selections.append(
                        Selection(
                            id=f"bf_fb_{i}_{j}",
                            name=sel_name,
                            back_price=price,
                            lay_price=round(price + random.uniform(0.01, 0.1), 2),
                            implied_probability=round(1.0 / price, 4),
                        )
                    )
                markets.append(
                    PlatformMarket(
                        platform=Platform.BETFAIR,
                        market_id=f"bf_football_{i}",
                        event_name=name,
                        market_name="Match Odds",
                        sport=SportType.FOOTBALL,
                        selections=selections,
                        start_time=now + timedelta(hours=random.randint(1, 24)),
                    )
                )

        if sport != SportType.FOOTBALL:
            for i, (name, sels) in enumerate(demo_racing):
                selections = []
                for j, sel_name in enumerate(sels):
                    price = round(random.uniform(2.0, 15.0), 2)
                    selections.append(
                        Selection(
                            id=f"bf_hr_{i}_{j}",
                            name=sel_name,
                            back_price=price,
                            lay_price=round(price + random.uniform(0.02, 0.2), 2),
                            implied_probability=round(1.0 / price, 4),
                        )
                    )
                markets.append(
                    PlatformMarket(
                        platform=Platform.BETFAIR,
                        market_id=f"bf_racing_{i}",
                        event_name=name,
                        market_name="Win",
                        sport=SportType.HORSE_RACING,
                        selections=selections,
                        start_time=now + timedelta(hours=random.randint(1, 12)),
                    )
                )
        return markets

    def _demo_prices(self, market_ids: list[str]) -> dict[str, list[Selection]]:
        import random

        result = {}
        for mid in market_ids:
            n = random.randint(2, 4)
            sels = []
            for j in range(n):
                price = round(random.uniform(1.5, 10.0), 2)
                sels.append(
                    Selection(
                        id=f"{mid}_sel_{j}",
                        name=f"Selection {j}",
                        back_price=price,
                        lay_price=round(price + random.uniform(0.01, 0.1), 2),
                        implied_probability=round(1.0 / price, 4),
                    )
                )
            result[mid] = sels
        return result
