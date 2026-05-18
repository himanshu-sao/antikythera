import React, { useState, useEffect } from 'react';
import {
  DndContext,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates
} from '@dnd-kit/sortable';
import { KanbanColumn } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import type { PipelineItem, PipelineState } from './types';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

export default function App() {
  const [state, setState] = useState<PipelineState>({ items: {} });
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

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

    const interval = setInterval(fetchState, 10000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        clearInterval(interval);
      } else {
        fetchState();
        // In a more robust implementation, we would restart the interval here.
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const itemId = active.id as string;
    const overId = over.id as string;

    const item = state.items[itemId];
    if (!item) return;
    const fromStage = item.stage;

    // Determine the destination stage
    let toStage = '';
    if (STAGES.includes(overId)) {
      toStage = overId;
    } else {
      // If dropped over another item, use that item's stage
      const overItem = state.items[overId];
      if (overItem) {
        toStage = overItem.stage;
      }
    }

    if (toStage && fromStage !== toStage) {
      try {
        const res = await fetch('http://localhost:8000/api/move', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: itemId, new_stage: toStage }),
        });
        if (res.ok) {
          await fetchState();
        }
      } catch (e) {
        console.error("Failed to move item", e);
      }
    }
  };

  if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Hermes Pipeline</h1>
          <p className="text-gray-500">Manage automation ideas and agent progress</p>
        </div>
        <button
          onClick={fetchState}
          className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
        >
          Refresh
        </button>
      </header>

      <div className="flex overflow-x-auto gap-6 pb-8 h-[calc(100vh-200px)]">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragEnd={handleDragEnd}
        >
          {STAGES.map(stage => (
            <KanbanColumn
              key={stage}
              id={stage}
              items={Object.entries(state.items)
                .filter(([_, item]) => item.stage === stage)
                .map(([id, item]) => ({ ...item, id }))}
              onCardClick={(id) => setSelectedId(id)}
            />
          ))}
        </DndContext>
      </div>

      {selectedId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-100">
              <h2 className="text-xl font-bold text-gray-900">{selectedId}</h2>
              <button
                onClick={() => setSelectedId(null)}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ArtifactViewer itemId={selectedId} onClose={() => setSelectedId(null)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
