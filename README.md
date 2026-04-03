# Betfair → Polymarket Automated Trading Bot

Cross-platform arbitrage trading bot that monitors Betfair UK and Polymarket, detects price discrepancies, and automatically executes trades on Polymarket.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Betfair UK  │────▶│   Trading Bot    │────▶│  Polymarket  │
│  (data feed) │     │  (Python/FastAPI) │     │  (execution) │
└─────────────┘     └────────┬─────────┘     └──────────────┘
                             │ WebSocket
                    ┌────────▼─────────┐
                    │   React Dashboard │
                    │   (real-time UI)  │
                    └──────────────────┘
```

## Features

- **Real-time price monitoring** — polls Betfair & Polymarket markets simultaneously
- **Fuzzy market matching** — automatically pairs equivalent events across platforms
- **Opportunity detection** — identifies price discrepancies above configurable threshold
- **Automated trade execution** — places entry/exit orders on Polymarket
- **Risk management** — position limits, daily loss limits, automatic halt
- **Live dashboard** — React web UI with market overview, trade log, P/L chart
- **Demo mode** — runs with simulated data (no API keys required)

## Supported Markets

- UK Football (Premier League, Championship, etc.)
- UK/Ireland Horse Racing (Ascot, Cheltenham, Leopardstown, etc.)

## Quick Start

### Demo Mode (no API keys needed)

```bash
# Clone and setup
cp .env.example .env

# With Docker
docker-compose up --build

# Or manually:
# Backend
cd backend
pip install -r requirements.txt
python -m src.main

# Dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

### Production Mode

1. **Betfair setup:**
   - Register at [betfair.com](https://www.betfair.com)
   - Join [Developer Program](https://developer.betfair.com)
   - Generate Application Key
   - Create SSL certificate for bot login

2. **Polymarket setup:**
   - Create account at [polymarket.com](https://polymarket.com)
   - Export private key (Settings → Export Private Key)
   - Fund wallet with USDC on Polygon

3. **Configure `.env`:**
   ```
   DEMO_MODE=false
   BETFAIR_USERNAME=...
   BETFAIR_PASSWORD=...
   BETFAIR_APP_KEY=...
   POLYMARKET_PRIVATE_KEY=0x...
   ```

4. Run: `docker-compose up --build`

## How It Works

1. **Market Discovery** — fetches upcoming markets from both platforms
2. **Market Matching** — uses fuzzy string matching + time comparison to pair events
3. **Price Monitoring** — continuously polls prices (Betfair ~500ms, Polymarket real-time)
4. **Opportunity Detection** — calculates edge:
   ```
   Betfair implied probability = 1 / decimal_odds
   Edge = |Betfair_implied% - Polymarket_price%|
   ```
5. **Trade Execution** — when edge > threshold (default 2%):
   - If Betfair prob > Polymarket price → BUY on Polymarket
   - If Betfair prob < Polymarket price → SELL on Polymarket
6. **Exit Management** — monitors for profit target or stop-loss

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI, asyncio |
| Betfair API | betfairlightweight |
| Polymarket API | py-clob-client, httpx |
| Database | SQLite (SQLAlchemy) |
| Frontend | React 18, TypeScript, Vite |
| Styling | TailwindCSS |
| Charts | Recharts |
| Deployment | Docker Compose |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Bot status, connections, risk |
| `GET /api/markets` | Active matched markets |
| `GET /api/trades` | Trade history |
| `GET /api/trades/active` | Open positions |
| `GET /api/trades/summary` | Win rate, total P/L |
| `GET /api/pnl` | Daily P/L for chart |
| `GET /api/opportunities` | Detected opportunities |
| `POST /api/bot/start` | Start bot |
| `POST /api/bot/stop` | Stop bot |
| `WS /ws` | Real-time updates |

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `true` | Run with simulated data |
| `MIN_EDGE_PERCENT` | `2.0` | Minimum edge to trigger trade |
| `MAX_POSITION_USDC` | `100.0` | Max USDC per position |
| `MAX_DAILY_LOSS_USDC` | `50.0` | Daily loss limit (auto-halt) |
| `POLL_INTERVAL_MS` | `500` | Price polling interval |

## License

MIT
