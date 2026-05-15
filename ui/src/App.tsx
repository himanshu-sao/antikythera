import React, { useState, useEffect } from 'react';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", 
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

export default function App() {
  const [state, setState] = useState({ items: {} });
  const [loading, setLoading] = useState(true);

  const fetchState = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/state');
      const data = await res.json();
      setState(data);
    } catch (e) {
      console.error("Failed to fetch state", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchState();
  }, []);

  const moveItem = async (itemId: string, newStage: string) => {
    try {
      const res = await fetch('http://localhost:8000/api/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, new_stage: newStage }),
      });
      if (res.ok) {
        await fetchState();
      }
    } catch (e) {
      console.error("Failed to move item", e);
    }
  };

  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <h1 className="text-3xl font-bold mb-8 text-center">Hermes Kanban Board</h1>
      <div className="flex overflow-x-auto gap-4 pb-4">
        {STAGES.map(stage => (
          <div key={stage} className="flex-shrink-0 w-64 bg-gray-200 rounded-lg p-4 flex flex-col">
            <h2 className="font-semibold mb-4 text-gray-700 border-b border-gray-300 pb-2">{stage}</h2>
            <div className="space-y-3">
              {Object.entries(state.items).filter(([_, item]: any) => item.stage === stage).map(([id, item]: any) => (
                <div 
                  key={id} 
                  className="bg-white p-3 rounded shadow cursor-pointer hover:bg-blue-50 transition-colors"
                  onClick={() => {
                    const nextStage = STAGES[STAGES.indexOf(stage) + 1];
                    if (nextStage) moveItem(id, nextStage);
                  }}
                >
                  <div className="text-xs font-bold text-gray-500">{id}</div>
                  <div className="text-sm font-medium text-gray-900">{item.title}</div>
                  <div className="text-xs text-gray-400 mt-2">Priority: {item.priority}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="text-center mt-8 text-gray-500 text-sm">Click a card to move it to the next stage.</p>
    </div>
  );
}
