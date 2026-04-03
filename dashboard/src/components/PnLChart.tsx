import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

interface PnLData {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
}

interface Summary {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl_usdc: number;
  win_rate: number;
  largest_win_usdc: number;
  largest_loss_usdc: number;
}

export default function PnLChart() {
  const [data, setData] = useState<PnLData[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const [pnlRes, sumRes] = await Promise.all([
          fetch("/api/pnl?days=30"),
          fetch("/api/trades/summary"),
        ]);
        setData(await pnlRes.json());
        setSummary(await sumRes.json());
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  const statCard = (label: string, value: string, color = "text-white") => (
    <div className="bg-gray-800/50 rounded-lg px-4 py-3">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`font-mono font-semibold ${color}`}>{value}</div>
    </div>
  );

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800">
        <h2 className="font-semibold">Profit / Loss</h2>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-5 pt-4">
          {statCard(
            "Total P/L",
            `${summary.total_pnl_usdc >= 0 ? "+" : ""}$${summary.total_pnl_usdc.toFixed(2)}`,
            summary.total_pnl_usdc >= 0 ? "text-emerald-400" : "text-red-400"
          )}
          {statCard("Total Trades", String(summary.total_trades))}
          {statCard(
            "Win Rate",
            `${(summary.win_rate * 100).toFixed(1)}%`,
            summary.win_rate >= 0.5 ? "text-emerald-400" : "text-yellow-400"
          )}
          {statCard(
            "Largest Win",
            `+$${summary.largest_win_usdc.toFixed(2)}`,
            "text-emerald-400"
          )}
        </div>
      )}

      <div className="px-5 py-4 h-64">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                stroke="#6b7280"
                fontSize={11}
                tickFormatter={(d: string) => d.slice(5)}
              />
              <YAxis stroke="#6b7280" fontSize={11} tickFormatter={(v: number) => `$${v}`} />
              <Tooltip
                contentStyle={{
                  background: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#9ca3af" }}
                formatter={(value: number, name: string) => [
                  `$${value.toFixed(2)}`,
                  name === "cumulative_pnl" ? "Cumulative" : "Daily",
                ]}
              />
              <Area
                type="monotone"
                dataKey="cumulative_pnl"
                stroke="#10b981"
                strokeWidth={2}
                fill="url(#pnlGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            No P/L data yet...
          </div>
        )}
      </div>
    </div>
  );
}
