import React, { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { KanbanColumn } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import { WorkflowDiagram } from './components/WorkflowDiagram';
import { CardEditor } from './components/CardEditor';
import { CommentSection } from './components/CommentSection';
import { ErrorBoundary } from './components/ErrorBoundary';
import { apiUrl } from './config';
import type { PipelineItem, PipelineState } from './types';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

export default function App() {
  const [state, setState] = useState<PipelineState>({ items: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
    })
  );

  const fetchState = async () => {
    try {
      setError(null);
      const res = await fetch(`${apiUrl}/api/state`);
      if (!res.ok) throw new Error('Failed to fetch state');
      const data = await res.json();
      setState(data);
    } catch (e: any) {
      console.error("Failed to fetch state", e);
      setError(e.message || 'Failed to load data');
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

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const itemId = String(active.id);
    const toStage = String(over.id);
    if (!itemId || !toStage || itemId === toStage) return;
    try {
      const res = await fetch(`${apiUrl}/api/move`, {
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
  };

  const handleUpdateItem = async (updates: any) => {
    if (!selectedId) return;
    try {
      const res = await fetch(`${apiUrl}/api/item/${selectedId}`, {
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

    // ENH-09: Optimistic Update
    setState(prev => ({
      ...prev,
      items: {
        ...prev.items,
        [itemId]: {
          id: itemId,
          title: itemTitle,
          stage: 'INTAKE',
          priority: 'medium',
          confidence_score: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        } as PipelineItem
      }
    }));

    try {
      const res = await fetch(`${apiUrl}/api/items`, {
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
      await fetchState();
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

  // ENH-05: Loading and error states
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading pipeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-red-600 mb-4">Error: {error}</p>
          <button
            onClick={() => { setError(null); setLoading(true); fetchState(); }}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50 p-6">
        <header className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Hermes Pipeline</h1>
          <p className="text-gray-600">Manage automation ideas and agent progress</p>
          <div className="mt-4 flex gap-2">
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

                    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-5 gap-4">
          {STAGES.map(stage => (
            <KanbanColumn
              key={stage}
              id={stage}
              items={Object.entries(state.items)
                .filter(([, item]) => item.stage === stage)
                .map(([id, item]) => ({ ...item, id }))}
              onCardClick={(id) => {
                setSelectedId(id);
                setEditMode(false);
              }}
              onEditClick={(id) => {
                setSelectedId(id);
                setEditMode(true);
              }}
            />
          ))}
        </div>
                                  </DndContext>

        {showWorkflow && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">Workflow Guide</h2>
                <button
                  onClick={() => setShowWorkflow(false)}
                  className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                >
                  ✕
                </button>
              </div>
              <WorkflowDiagram onClose={() => setShowWorkflow(false)} />
            </div>
          </div>
        )}

        {selectedId && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto p-6 w-full">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">{selectedId}</h2>
                <div className="flex gap-2 items-center">
                  {!editMode && (
                    <button
                      onClick={() => setEditMode(true)}
                      className="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-md text-xs font-medium hover:bg-indigo-100 transition-colors"
                    >
                      Edit Details
                    </button>
                  )}
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
              </div>
              {editMode ? (
                <CardEditor
                  itemId={selectedId}
                  initialData={{
                    title: state.items[selectedId].title,
                    description: state.items[selectedId].description,
                    priority: state.items[selectedId].priority,
                    confidence_score: state.items[selectedId].confidence_score ?? 0
                  }}
                  onSave={handleUpdateItem}
                  onClose={() => setEditMode(false)}
                />
              ) : (
                <ErrorBoundary>
                  <ArtifactViewer itemId={selectedId} onClose={() => setSelectedId(null)} />
                </ErrorBoundary>
              )}
            </div>
          </div>
        )}

        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h2 className="text-xl font-bold mb-4">Create New Idea</h2>
              <p className="text-sm text-gray-600 mb-4">Enter a unique ID (e.g., IDEA-1) and a title.</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Item ID</label>
                  <input
                    type="text"
                    value={newItem.id}
                    onChange={(e) => setNewItem({ ...newItem, id: e.target.value })}
                    placeholder="e.g. IDEA-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                  <input
                    type="text"
                    value={newItem.title}
                    onChange={(e) => setNewItem({ ...newItem, title: e.target.value })}
                    placeholder="What is the automation idea?"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                  />
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateItem}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
                >
                  Create Item
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
