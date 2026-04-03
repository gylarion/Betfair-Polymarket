from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.websocket import ws_manager

if TYPE_CHECKING:
    from src.main import BotOrchestrator

router = APIRouter()
_bot: BotOrchestrator | None = None


def set_bot(bot: BotOrchestrator):
    global _bot
    _bot = bot


@router.get("/api/status")
async def get_status():
    if not _bot:
        return {"status": "not_initialized"}
    return {
        "status": "running" if _bot.running else "stopped",
        "demo_mode": _bot.settings.bot.demo_mode,
        "betfair_connected": _bot.betfair.is_connected,
        "polymarket_connected": _bot.polymarket.is_connected,
        "matched_markets": len(_bot.matcher.get_matched()),
        "active_trades": len(_bot.executor.get_active_trades()),
        "ws_connections": ws_manager.active_count,
        "risk": _bot.risk.get_status(),
    }


@router.get("/api/markets")
async def get_markets():
    if not _bot:
        return []
    matched = _bot.matcher.get_matched()
    result = []
    for mid, mm in matched.items():
        result.append({
            "id": mm.id,
            "event_name": mm.betfair.event_name,
            "sport": mm.betfair.sport.value,
            "confidence": mm.match_confidence,
            "betfair": {
                "market_id": mm.betfair.market_id,
                "selections": [
                    {
                        "name": s.name,
                        "back_price": s.back_price,
                        "implied_prob": s.implied_probability,
                    }
                    for s in mm.betfair.selections
                ],
                "last_updated": mm.betfair.last_updated.isoformat(),
            },
            "polymarket": {
                "market_id": mm.polymarket.market_id,
                "question": mm.polymarket.market_name,
                "selections": [
                    {
                        "name": s.name,
                        "price_cents": round(s.implied_probability * 100, 1) if s.implied_probability else None,
                    }
                    for s in mm.polymarket.selections
                ],
                "last_updated": mm.polymarket.last_updated.isoformat(),
            },
        })
    return result


@router.get("/api/trades")
async def get_trades(limit: int = 50):
    if not _bot:
        return []
    trades = _bot.db.get_trades(limit=limit)
    return [t.model_dump() for t in trades]


@router.get("/api/trades/active")
async def get_active_trades():
    if not _bot:
        return []
    return [t.model_dump() for t in _bot.executor.get_active_trades()]


@router.get("/api/trades/summary")
async def get_trade_summary():
    if not _bot:
        return {}
    return _bot.db.get_trade_summary().model_dump()


@router.get("/api/pnl")
async def get_pnl(days: int = 30):
    if not _bot:
        return []
    return _bot.db.get_daily_pnl(days=days)


@router.get("/api/opportunities")
async def get_opportunities(limit: int = 50):
    if not _bot:
        return []
    return [o.model_dump() for o in _bot.detector.get_recent(limit=limit)]


@router.post("/api/bot/start")
async def start_bot():
    if _bot and not _bot.running:
        import asyncio
        asyncio.create_task(_bot.run())
        return {"status": "starting"}
    return {"status": "already_running" if _bot else "not_initialized"}


@router.post("/api/bot/stop")
async def stop_bot():
    if _bot and _bot.running:
        await _bot.stop()
        return {"status": "stopped"}
    return {"status": "not_running"}


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
