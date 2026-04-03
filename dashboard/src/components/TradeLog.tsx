import { useEffect, useState } from "react";
import { ArrowUpRight, ArrowDownRight, Clock, CheckCircle, XCircle } from "lucide-react";

interface Trade {
  id: string;
  selection_name: string;
  entry_side: string;
  entry_price: number;
  entry_size_usdc: number;
  exit_price: number | null;
  edge_percent: number;
  status: string;
  pnl_usdc: number | null;
  created_at: string;
}

const statusIcon: Record<string, JSX.Element> = {
  completed: <CheckCircle size={14} className="text-emerald-400" />,
  entry_filled: <Clock size={14} className="text-blue-400" />,
  failed: <XCircle size={14} className="text-red-400" />,
  pending: <Clock size={14} className="text-gray-400" />,
};

export default function TradeLog() {
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/trades?limit=30");
        setTrades(await res.json());
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold">Trade Log</h2>
        <span className="text-xs text-gray-500">{trades.length} trades</span>
      </div>
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-900">
            <tr className="text-gray-400 text-xs border-b border-gray-800">
              <th className="text-left px-5 py-2">Selection</th>
              <th className="px-3 py-2">Side</th>
              <th className="px-3 py-2">Entry</th>
              <th className="px-3 py-2">Exit</th>
              <th className="px-3 py-2">Size</th>
              <th className="px-3 py-2">Edge</th>
              <th className="px-3 py-2">P/L</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="px-5 py-2.5 font-medium">{t.selection_name}</td>
                <td className="px-3 py-2.5 text-center">
                  {t.entry_side === "buy" ? (
                    <span className="inline-flex items-center gap-1 text-emerald-400">
                      <ArrowUpRight size={14} /> BUY
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-red-400">
                      <ArrowDownRight size={14} /> SELL
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-center font-mono">{t.entry_price.toFixed(1)}¢</td>
                <td className="px-3 py-2.5 text-center font-mono">
                  {t.exit_price ? `${t.exit_price.toFixed(1)}¢` : "—"}
                </td>
                <td className="px-3 py-2.5 text-center font-mono">${t.entry_size_usdc.toFixed(2)}</td>
                <td className="px-3 py-2.5 text-center font-mono text-yellow-400">
                  {t.edge_percent.toFixed(1)}%
                </td>
                <td className="px-3 py-2.5 text-center font-mono">
                  {t.pnl_usdc !== null ? (
                    <span className={t.pnl_usdc >= 0 ? "text-emerald-400" : "text-red-400"}>
                      {t.pnl_usdc >= 0 ? "+" : ""}${t.pnl_usdc.toFixed(4)}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-3 py-2.5 text-center">
                  <span className="inline-flex items-center gap-1">
                    {statusIcon[t.status] || statusIcon.pending}
                    <span className="text-xs capitalize">{t.status.replace("_", " ")}</span>
                  </span>
                </td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-8 text-gray-500">
                  No trades yet...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
