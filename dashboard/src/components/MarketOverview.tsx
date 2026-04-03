import { useEffect, useState } from "react";

interface Selection {
  name: string;
  back_price?: number | null;
  implied_prob?: number | null;
  price_cents?: number | null;
}

interface Market {
  id: string;
  event_name: string;
  sport: string;
  confidence: number;
  betfair: {
    market_id: string;
    selections: Selection[];
    last_updated: string;
  };
  polymarket: {
    market_id: string;
    question: string;
    selections: Selection[];
    last_updated: string;
  };
}

export default function MarketOverview() {
  const [markets, setMarkets] = useState<Market[]>([]);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("/api/markets");
        setMarkets(await res.json());
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  const sportBadge = (sport: string) => {
    const colors: Record<string, string> = {
      football: "bg-blue-500/20 text-blue-400",
      horse_racing: "bg-orange-500/20 text-orange-400",
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded ${colors[sport] || "bg-gray-700 text-gray-300"}`}>
        {sport === "horse_racing" ? "Racing" : "Football"}
      </span>
    );
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold">Active Markets</h2>
        <span className="text-xs text-gray-500">{markets.length} matched</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-xs border-b border-gray-800">
              <th className="text-left px-5 py-2">Event</th>
              <th className="px-3 py-2">Sport</th>
              <th className="px-3 py-2">Match %</th>
              <th className="px-3 py-2">Betfair Price</th>
              <th className="px-3 py-2">Betfair Prob</th>
              <th className="px-3 py-2">Polymarket</th>
              <th className="px-3 py-2">Edge</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => {
              const bfSel = m.betfair.selections[0];
              const pmSel = m.polymarket.selections[0];
              const bfProb = bfSel?.implied_prob ?? 0;
              const pmPrice = pmSel?.price_cents ?? 0;
              const edge = Math.abs(bfProb * 100 - pmPrice);

              return (
                <tr key={m.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-5 py-3">
                    <div className="font-medium text-white">{m.event_name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{m.polymarket.question}</div>
                  </td>
                  <td className="px-3 py-3 text-center">{sportBadge(m.sport)}</td>
                  <td className="px-3 py-3 text-center">{(m.confidence * 100).toFixed(0)}%</td>
                  <td className="px-3 py-3 text-center font-mono">
                    {bfSel?.back_price?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-3 py-3 text-center font-mono">
                    {bfProb ? `${(bfProb * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-3 py-3 text-center font-mono">
                    {pmPrice ? `${pmPrice.toFixed(1)}¢` : "—"}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span
                      className={`font-mono font-medium ${
                        edge >= 2 ? "text-emerald-400" : edge >= 1 ? "text-yellow-400" : "text-gray-500"
                      }`}
                    >
                      {edge.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              );
            })}
            {markets.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-gray-500">
                  No matched markets yet...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
