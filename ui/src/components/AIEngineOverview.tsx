import React from 'react';

// Placeholder Overview component – in a real product this would render charts
// (e.g., using chart.js, recharts, or d3). For now we just show static stats.
export function AIEngineOverview() {
  return (
    <div className="p-4 bg-gray-50 rounded-lg border">
      <h2 className="text-lg font-bold mb-2">Engine Overview</h2>
      <p className="text-sm text-gray-600 mb-2">Graphs and additional datapoints will appear here.</p>
      <div className="grid grid-cols-2 gap-4">
        <div className="p-2 bg-white rounded shadow">
          <p className="text-xs text-gray-500">Models Loaded</p>
          <p className="text-xl font-semibold">4</p>
        </div>
        <div className="p-2 bg-white rounded shadow">
          <p className="text-xs text-gray-500">Requests Today</p>
          <p className="text-xl font-semibold">128</p>
        </div>
        <div className="p-2 bg-white rounded shadow">
          <p className="text-xs text-gray-500">Avg Latency (ms)</p>
          <p className="text-xl font-semibold">45</p>
        </div>
        <div className="p-2 bg-white rounded shadow">
          <p className="text-xs text-gray-500">Errors (last 24h)</p>
          <p className="text-xl font-semibold text-red-600">2</p>
        </div>
      </div>
    </div>
  );
}
