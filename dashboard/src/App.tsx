import StatusBar from "./components/StatusBar";
import MarketOverview from "./components/MarketOverview";
import TradeLog from "./components/TradeLog";
import PnLChart from "./components/PnLChart";
import OpportunityFeed from "./components/OpportunityFeed";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <StatusBar />
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <PnLChart />
          </div>
          <div>
            <OpportunityFeed />
          </div>
        </div>
        <MarketOverview />
        <TradeLog />
      </main>
    </div>
  );
}
