import React, { useState, useEffect } from 'react';
import { monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter';
import { KanbanColumn } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import { WorkflowDiagram } from './components/WorkflowDiagram';
import { CardEditor } from './components/CardEditor';
import { CommentSection } from './components/CommentSection';
import type { PipelineItem, PipelineState } from './types';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

export default function App() {
  const [state, setState] = useState<PipelineState>({ items: {} });
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [newItem, setNewItem] = useState({ id: '', title: '' });

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
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    return monitorForElements({
      onPerformOperation: async ({ event }) => {
        const dragData = event.info;
        const targetData = event.target;

        if (dragData && targetData) {
          const itemId = dragData.id;
          const toStage = targetData.columnId;

          // For intra-column reordering, we'd need the target card index.
          // For now, we'll just update the stage and use a default order.
          try {
            const res = await fetch('http://localhost:8000/api/move', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                item_id: itemId,
                new_stage: toStage,
                order: 0 // In a full implementation, we'd calculate the target index
              }),
            });
            if (res.ok) {
              await fetchState();
            }
          } catch (e) {
            console.error("Failed to move item", e);
          }
        }
      },
    });
  }, []);

  const handleUpdateItem = async (updates: any) => {
    if (!selectedId) return;
    try {
      const res = await fetch(`http://localhost:8000/api/item/${selectedId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to update item');
      }
      await fetchState();
    } catch (e: any) {
      console.error("Failed to update item", e);
      throw e;
    }
  };

  const handleCreateItem = async () => {
    if (!newItem.id || !newItem.title) return;

    const itemId = newItem.id.toUpperCase();
    const itemTitle = newItem.title;

    // Optimistic Update
    setState(prev => ({
      ...prev,
      items: {
        ...prev.items,
        [itemId]: {
          id: itemId,
          title: itemTitle,
          stage: 'INTAKE',
          priority: 'Medium',
          confidence_score: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      }
    }));

    try {
      const res = await fetch('http://localhost:8000/api/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, title: itemTitle }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to create item');
      }

      setShowCreateModal(false);
      setNewItem({ id: '', title: '' });
    } catch (e: any) {
      console.error("Failed to create item", e);
      alert(`Error: ${e.message}`);

      // Rollback optimistic update
      setState(prev => {
        const newItems = { ...prev.items };
        delete newItems[itemId];
        return { ...prev, items: newItems };
      });
    }
  };

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
        <div className="flex gap-3">
          <button
            onClick={() => setShowWorkflow(true)}
            className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
          >
            How it works
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
          >
            + New Idea
          </button>
          <button
            onClick={fetchState}
            className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="flex overflow-x-auto gap-6 pb-8 h-[calc(100vh-200px)]">
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
      </div>

      {showWorkflow && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-100">
              <h2 className="text-xl font-bold text-gray-900">Workflow Guide</h2>
              <button
                onClick={() => setShowWorkflow(false)}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <WorkflowDiagram onClose={() => setShowWorkflow(false)} />
            </div>
          </div>
        </div>
      )}

      {selectedId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-100">
              <div className="flex items-center gap-4">
                <h2 className="text-xl font-bold text-gray-900">{selectedId}</h2>
                {!editMode && (
                  <button
                    onClick={() => setEditMode(true)}
                    className="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-md text-xs font-medium hover:bg-indigo-100 transition-colors"
                  >
                    Edit Details
                  </button>
                )}
              </div>
              <button
                onClick={() => {
                  setSelectedId(null);
                  setEditMode(false);
                }}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {editMode ? (
                <CardEditor
                  itemId={selectedId}
                  initialData={{
                    title: state.items[selectedId]?.title || '',
                    description: state.items[selectedId]?.description || '',
                    priority: state.items[selectedId]?.priority || 'Medium',
                    confidence_score: state.items[selectedId]?.confidence_score || 0,
                  }}
                  onSave={handleUpdateItem}
                  onClose={() => setEditMode(false)}
                />
              ) : (
                <div className="flex flex-col h-full">
                  <div className="flex-1 overflow-hidden">
                    <ArtifactViewer itemId={selectedId} onClose={() => setSelectedId(null)} />
                  </div>
                  <CommentSection
                    itemId={selectedId}
                    initialComments={state.items[selectedId]?.comments || []}
                    onCommentAdded={fetchState}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="p-6 border-b border-gray-100">
              <h2 className="text-xl font-bold text-gray-900">Create New Idea</h2>
              <p className="text-sm text-gray-500">Enter a unique ID (e.g., IDEA-1) and a title.</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Item ID</label>
                <input
                  type="text"
                  value={newItem.id}
                  onChange={e => setNewItem({ ...newItem, id: e.target.value })}
                  placeholder="e.g. IDEA-1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={newItem.title}
                  onChange={e => setNewItem({ ...newItem, title: e.target.value })}
                  placeholder="What is the automation idea?"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                />
              </div>
            </div>
            <div className="p-6 bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateItem}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
              >
                Create Item
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
