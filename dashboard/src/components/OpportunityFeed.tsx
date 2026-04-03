import { useEffect, useState } from "react";
import { Zap } from "lucide-react";

interface Opportunity {
  id: string;
  selection_name: string;
  betfair_price: number;
  betfair_implied_prob: number;
  polymarket_price: number;
  edge_percent: number;
  suggested_side: string;
  suggested_size_usdc: number;
  status: string;
  detected_at: string;
}

export default function OpportunityFeed() {
  const [opps, setOpps] = useState<Opportunity[]>([]);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/opportunities?limit=20");
        setOpps(await res.json());
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  const statusColor: Record<string, string> = {
    detected: "text-yellow-400",
    executing: "text-blue-400",
    executed: "text-emerald-400",
    expired: "text-gray-500",
    skipped: "text-gray-500",
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
        <Zap size={16} className="text-yellow-400" />
        <h2 className="font-semibold">Opportunity Feed</h2>
      </div>
      <div className="max-h-80 overflow-y-auto divide-y divide-gray-800/50">
        {opps.map((o) => (
          <div key={o.id} className="px-5 py-3 hover:bg-gray-800/30">
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium">{o.selection_name}</span>
              <span className={`text-xs font-medium capitalize ${statusColor[o.status] || "text-gray-400"}`}>
                {o.status}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span>
                BF: <span className="font-mono text-gray-300">{o.betfair_price.toFixed(2)}</span>{" "}
                ({(o.betfair_implied_prob * 100).toFixed(1)}%)
              </span>
              <span>
                PM: <span className="font-mono text-gray-300">{o.polymarket_price.toFixed(1)}¢</span>
              </span>
              <span className="text-emerald-400 font-mono font-medium">
                Edge: {o.edge_percent.toFixed(1)}%
              </span>
              <span>
                {o.suggested_side.toUpperCase()} ${o.suggested_size_usdc.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
        {opps.length === 0 && (
          <div className="px-5 py-8 text-center text-gray-500">
            Scanning for opportunities...
          </div>
        )}
      </div>
    </div>
  );
}
