from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, Float, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import settings
from src.models.trade import Trade, TradeSummary


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    matched_market_id = Column(String, nullable=False, index=True)
    selection_name = Column(String, nullable=False)
    data = Column(Text, nullable=False)  # Full Trade JSON
    status = Column(String, nullable=False, index=True)
    pnl_usdc = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpportunityRecord(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    matched_market_id = Column(String, nullable=False, index=True)
    selection_name = Column(String, nullable=False)
    edge_percent = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    data = Column(Text, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self, url: str | None = None):
        self.engine = create_engine(url or settings.server.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def save_trade(self, trade: Trade) -> Trade:
        if not trade.id:
            trade.id = str(uuid.uuid4())
        with self.get_session() as session:
            record = session.get(TradeRecord, trade.id)
            if record:
                record.data = trade.model_dump_json()
                record.status = trade.status.value
                record.pnl_usdc = trade.pnl_usdc
                record.updated_at = datetime.utcnow()
            else:
                record = TradeRecord(
                    id=trade.id,
                    matched_market_id=trade.matched_market_id,
                    selection_name=trade.selection_name,
                    data=trade.model_dump_json(),
                    status=trade.status.value,
                    pnl_usdc=trade.pnl_usdc,
                )
                session.add(record)
            session.commit()
        return trade

    def get_trades(self, limit: int = 50, offset: int = 0) -> list[Trade]:
        with self.get_session() as session:
            records = (
                session.query(TradeRecord)
                .order_by(TradeRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [Trade.model_validate_json(r.data) for r in records]

    def get_trade_summary(self, since: datetime | None = None) -> TradeSummary:
        with self.get_session() as session:
            query = session.query(TradeRecord).filter(TradeRecord.status == "completed")
            if since:
                query = query.filter(TradeRecord.created_at >= since)
            records = query.all()

        trades = [Trade.model_validate_json(r.data) for r in records]
        if not trades:
            return TradeSummary()

        pnls = [t.pnl_usdc or 0.0 for t in trades]
        edges = [t.edge_percent for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        return TradeSummary(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_usdc=sum(pnls),
            avg_edge_percent=sum(edges) / len(edges) if edges else 0,
            largest_win_usdc=max(winning) if winning else 0,
            largest_loss_usdc=min(losing) if losing else 0,
            win_rate=len(winning) / len(trades) if trades else 0,
        )

    def get_daily_pnl(self, days: int = 30) -> list[dict]:
        with self.get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)
            records = (
                session.query(TradeRecord)
                .filter(TradeRecord.status == "completed")
                .filter(TradeRecord.created_at >= cutoff)
                .order_by(TradeRecord.created_at)
                .all()
            )

        daily: dict[str, float] = {}
        for r in records:
            day = r.created_at.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0.0) + (r.pnl_usdc or 0.0)

        cumulative = 0.0
        result = []
        for day, pnl in sorted(daily.items()):
            cumulative += pnl
            result.append({"date": day, "daily_pnl": round(pnl, 2), "cumulative_pnl": round(cumulative, 2)})
        return result


db = Database()
