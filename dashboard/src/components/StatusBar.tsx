import { useEffect, useState } from "react";
import { Activity, Wifi, WifiOff, TrendingUp, AlertTriangle } from "lucide-react";

interface Status {
  status: string;
  demo_mode: boolean;
  betfair_connected: boolean;
  polymarket_connected: boolean;
  matched_markets: number;
  active_trades: number;
  ws_connections: number;
  risk: {
    halted: boolean;
    daily_pnl: number;
    max_daily_loss: number;
    total_exposure: number;
  };
}

export default function StatusBar() {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/status");
        setStatus(await res.json());
      } catch {
        setStatus(null);
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!status) {
    return (
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-3">
        <span className="text-gray-500">Connecting to backend...</span>
      </div>
    );
  }

  const Dot = ({ ok }: { ok: boolean }) => (
    <span className={`inline-block w-2 h-2 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`} />
  );

  return (
    <div className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-6 text-sm">
      <div className="flex items-center gap-2 font-semibold text-white">
        <Activity size={18} className="text-emerald-400" />
        Betfair → Polymarket Bot
      </div>

      {status.demo_mode && (
        <span className="bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded text-xs font-medium">
          DEMO
        </span>
      )}

      <div className="flex items-center gap-1.5">
        <Dot ok={status.betfair_connected} />
        Betfair
      </div>

      <div className="flex items-center gap-1.5">
        <Dot ok={status.polymarket_connected} />
        Polymarket
      </div>

      <div className="text-gray-400">
        {status.matched_markets} markets
      </div>

      <div className="flex items-center gap-1.5">
        <TrendingUp size={14} />
        {status.active_trades} active trades
      </div>

      {status.risk.halted && (
        <div className="flex items-center gap-1.5 text-red-400">
          <AlertTriangle size={14} />
          HALTED
        </div>
      )}

      <div className="ml-auto flex items-center gap-4 text-gray-400">
        <span>
          Daily P/L:{" "}
          <span className={status.risk.daily_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
            ${status.risk.daily_pnl.toFixed(2)}
          </span>
        </span>
        <span>Exposure: ${status.risk.total_exposure.toFixed(2)}</span>
      </div>
    </div>
  );
}
