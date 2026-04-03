from __future__ import annotations

import logging
import re
import uuid
from difflib import SequenceMatcher

from src.models.market import MatchedMarket, PlatformMarket, SportType

logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize event name for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r"\b(fc|afc|cf|sc|united|utd|city)\b", "", name)
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def extract_team_names(event_name: str) -> list[str]:
    """Extract team/horse names from an event name."""
    separators = [" vs ", " v ", " - ", " against "]
    for sep in separators:
        if sep in event_name.lower():
            parts = re.split(re.escape(sep), event_name, flags=re.IGNORECASE)
            return [p.strip() for p in parts if p.strip()]
    return [event_name.strip()]


class MarketMatcher:
    """Matches markets between Betfair and Polymarket based on event similarity."""

    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self._matched: dict[str, MatchedMarket] = {}

    def match_markets(
        self,
        betfair_markets: list[PlatformMarket],
        polymarket_markets: list[PlatformMarket],
    ) -> list[MatchedMarket]:
        matched = []
        used_poly_ids: set[str] = set()

        for bf in betfair_markets:
            best_match: PlatformMarket | None = None
            best_score = 0.0

            for pm in polymarket_markets:
                if pm.market_id in used_poly_ids:
                    continue
                if bf.sport != pm.sport:
                    continue

                score = self._compute_match_score(bf, pm)
                if score > best_score:
                    best_score = score
                    best_match = pm

            if best_match and best_score >= self.min_confidence:
                used_poly_ids.add(best_match.market_id)
                sel_mapping = self._map_selections(bf, best_match)
                mid = str(uuid.uuid4())[:8]

                mm = MatchedMarket(
                    id=mid,
                    betfair=bf,
                    polymarket=best_match,
                    match_confidence=round(best_score, 3),
                    selection_mapping=sel_mapping,
                )
                matched.append(mm)
                self._matched[mid] = mm
                logger.info(
                    f"Matched: {bf.event_name} <-> {best_match.event_name} "
                    f"(confidence: {best_score:.2f})"
                )

        return matched

    def _compute_match_score(self, bf: PlatformMarket, pm: PlatformMarket) -> float:
        event_sim = similarity(bf.event_name, pm.event_name)
        bf_teams = extract_team_names(bf.event_name)
        pm_text = pm.event_name.lower() + " " + pm.market_name.lower()

        team_score = 0.0
        for team in bf_teams:
            if normalize_name(team) in pm_text.lower():
                team_score += 1.0
        if bf_teams:
            team_score /= len(bf_teams)

        time_score = 0.0
        if bf.start_time and pm.start_time:
            diff = abs((bf.start_time - pm.start_time).total_seconds())
            if diff < 3600:
                time_score = 1.0
            elif diff < 86400:
                time_score = 0.5

        return event_sim * 0.4 + team_score * 0.4 + time_score * 0.2

    def _map_selections(self, bf: PlatformMarket, pm: PlatformMarket) -> dict[str, str]:
        """Map Betfair selection IDs to Polymarket token IDs."""
        mapping = {}

        for bf_sel in bf.selections:
            best_pm_sel = None
            best_score = 0.0
            for pm_sel in pm.selections:
                if pm_sel.id in mapping.values():
                    continue

                score = similarity(bf_sel.name, pm_sel.name)
                bf_name_lower = bf_sel.name.lower()
                pm_name_lower = pm_sel.name.lower()

                if pm_name_lower == "yes" and bf_name_lower in pm.market_name.lower():
                    score = max(score, 0.9)
                if bf_name_lower in pm_name_lower or pm_name_lower in bf_name_lower:
                    score = max(score, 0.8)

                if score > best_score:
                    best_score = score
                    best_pm_sel = pm_sel

            if best_pm_sel and best_score > 0.3:
                mapping[bf_sel.id] = best_pm_sel.id

        return mapping

    def get_matched(self) -> dict[str, MatchedMarket]:
        return self._matched

    def update_prices(self, market_id: str, bf: PlatformMarket | None = None, pm: PlatformMarket | None = None):
        if market_id in self._matched:
            if bf:
                self._matched[market_id].betfair = bf
            if pm:
                self._matched[market_id].polymarket = pm
