import React, { useState, useEffect } from 'react';
import {
  DndContext, 
  closestCenter, 
  KeyboardSensor, 
  PointerSensor, 
  useSensor, 
  useSensors, 
  DragEndEvent
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import toast, { Toaster } from 'react-hot-toast';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", 
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

function SortableItem({ id, item }: { id: string, item: any }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      {...attributes} 
      {...listeners}
      className="bg-white p-3 rounded shadow cursor-grab active:cursor-grabbing hover:bg-blue-50 transition-colors border border-gray-200"
    >
      <div className="text-xs font-bold text-gray-500">{id}</div>
      <div className="text-sm font-medium text-gray-900">{item.title}</div>
      <div className="text-xs text-gray-400 mt-2">Priority: {item.priority}</div>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState({ items: {} });
  const [loading, setLoading] = useState(true);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const fetchState = async () => {
    try {
      const res = await fetch('/api/state');
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

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    if (activeId === overId) return;

    let newStage = '';
    if (STAGES.includes(overId)) {
      newStage = overId;
    } else {
      const item = state.items[overId];
      if (item) {
        newStage = item.stage;
      }
    }

    if (newStage) {
      await moveItem(activeId, newStage);
    }
  };

  const moveItem = async (itemId: string, newStage: string) => {
    try {
      const res = await fetch('/api/move', {
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
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <Toaster position="top-right" />
        <div className="flex overflow-x-auto gap-4 pb-4">
          {STAGES.map(stage => (
            <div 
              key={stage} 
              id={stage}
              className="flex-shrink-0 w-64 bg-gray-200 rounded-lg p-4 flex flex-col"
            >
              <h2 className="font-semibold mb-4 text-gray-700 border-b border-gray-300 pb-2">{stage}</h2>
              <SortableContext 
                id={stage} 
                items={Object.entries(state.items)
                  .filter(([_, item]: any) => item.stage === stage)
                  .map(([id]) => id)
                } 
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-3 min-h-[100px]">
                  {Object.entries(state.items)
                    .filter(([_, item]: any) => item.stage === stage)
                    .map(([id, item]: any) => (
                      <SortableItem key={id} id={id} item={item} />
                    ))
                  }
                </div>
              </SortableContext>
            </div>
          ))}
        </div>
      </DndContext>
      <p className="text-center mt-8 text-gray-500 text-sm">Drag and drop cards to move them between stages.</p>
    </div>
  );
}
