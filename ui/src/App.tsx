import React, { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, DragStartEvent, PointerSensor, useSensor, useSensors, DragOverlay } from '@dnd-kit/core';
import { KanbanColumn, KanbanCardContent } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import { WorkflowDiagram } from './components/WorkflowDiagram';
import { CardEditor } from './components/CardEditor';
import { CommentSection } from './components/CommentSection';
import { ErrorBoundary } from './components/ErrorBoundary';
import { apiUrl } from './config';
import toast, { Toaster } from 'react-hot-toast';
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
  const [activeId, setActiveId] = useState<string | null>(null);
  const [newItem, setNewItem] = useState({ id: '', title: '', source_type: '', source_value: '', due_date: '' });
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');


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

    let interval = setInterval(fetchState, 10000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        clearInterval(interval);
      } else {
        fetchState();
        clearInterval(interval);
        interval = setInterval(fetchState, 10000);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedId(null);
        setEditMode(false);
        setShowCreateModal(false);
        setShowWorkflow(false);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedId]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(String(event.active.id));
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const itemId = String(active.id);
    const overId = String(over.id);
    if (!itemId || !overId) return;

    const activeItem = state.items[itemId];
    if (!activeItem) return;

    let targetStage = '';
    let targetOrder = 0;

    const isStage = STAGES.includes(overId);
    if (isStage) {
      targetStage = overId;
      const columnItems = Object.entries(state.items)
        .map(([id, item]) => ({ ...item, id }))
        .filter(item => item.stage === targetStage && item.id !== itemId)
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
      targetOrder = columnItems.length;
    } else {
      const overItem = state.items[overId];
      if (!overItem) return;
      targetStage = overItem.stage;

      const columnItems = Object.entries(state.items)
        .map(([id, item]) => ({ ...item, id }))
        .filter(item => item.stage === targetStage && item.id !== itemId)
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

      const overIndex = columnItems.findIndex(item => item.id === overId);
      if (overIndex === -1) {
        targetOrder = columnItems.length;
      } else {
        targetOrder = overIndex;
      }
    }

    if (activeItem.stage === targetStage && (activeItem.order ?? 0) === targetOrder) {
      return;
    }

    try {
      const res = await fetch(`${apiUrl}/api/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemId,
          new_stage: targetStage,
          order: targetOrder,
        }),
      });
      if (res.ok) {
        const freshState = await fetchState();
        if (!freshState) return;

        // Calculate the final order for the target column using the fresh state
        const columnItems = Object.entries(freshState.items)
          .filter(([, item]: [string, any]) => item.stage === targetStage)
          .map(([id, item]: [string, any]) => ({ ...item, id }))
          .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

        const orderedIds = columnItems.map(item => item.id);

        await fetch(`${apiUrl}/api/items/reorder`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            stage: targetStage,
            ordered_ids: orderedIds,
          }),
        });

        // Final refresh to ensure UI is perfectly synced with the reordered state
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

  const handleDeleteItem = async (itemId?: string) => {
    const idToDelete = itemId || selectedId;
    if (!idToDelete) return;
    try {
      const res = await fetch(`${apiUrl}/api/item/${idToDelete}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to delete item');
      }
      if (itemId) {
        setSelectedId(null);
      }
      setEditMode(false);
      await fetchState();
    } catch (e: any) {
      console.error("Failed to delete item", e);
      throw e;
    }
  };

  const handleCreateItem = async () => {
    if (!newItem.id || !newItem.title) return;
    const itemId = newItem.id.toUpperCase();
    const itemTitle = newItem.title;
    const sourceType = newItem.source_type || undefined;
    const sourceValue = newItem.source_value || undefined;
    const dueDate = newItem.due_date || undefined;

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
          source_type: sourceType,
          source_value: sourceValue,
          due_date: dueDate,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        } as PipelineItem
      }
    }));

    try {
      const res = await fetch(`${apiUrl}/api/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemId,
          title: itemTitle,
          source_type: sourceType,
          source_value: sourceValue,
          due_date: dueDate,
        }),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to create item');
      }
      setShowCreateModal(false);
      setNewItem({ id: '', title: '', source_type: '', source_value: '', due_date: '' });
      await fetchState();
    } catch (e: any) {
      console.error("Failed to create item", e);
      toast.error(`Error: ${e.message}`);
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
            <div className="ml-auto flex items-center gap-3">
              <div className="flex items-center gap-2">
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all bg-white"
                >
                  <option value="all">All Priorities</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>

                <select
                  value={stageFilter}
                  onChange={(e) => setStageFilter(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all bg-white"
                >
                  <option value="all">All Stages</option>
                  {STAGES.map(stage => (
                    <option key={stage} value={stage}>{stage}</option>
                  ))}
                </select>
              </div>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.3-4.3" />
                  </svg>
                </span>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search ideas..."
                  className="pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all w-64"
                />
              </div>
            </div>
          </div>
        </header>

        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <Toaster position="top-right" />
          <div className="grid grid-cols-5 gap-4">
            {STAGES.map(stage => (
              <KanbanColumn
                key={stage}
                id={stage}
                items={Object.entries(state.items)
                  .filter(([, item]) => item.stage === stage)
                  .filter(([, item]) => {
                    const matchesSearch = !searchQuery ||
                      item.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.source_value?.toLowerCase().includes(searchQuery.toLowerCase());

                    const matchesPriority = priorityFilter === 'all' || item.priority?.toLowerCase() === priorityFilter;
                    const matchesStage = stageFilter === 'all' || item.stage === stageFilter;

                    return matchesSearch && matchesPriority && matchesStage;
                  })
                  .map(([id, item]) => ({ ...item, id }))
                  .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))}
                onCardClick={(id) => {
                  setSelectedId(id);
                  setEditMode(false);
                }}
                onEditClick={(id) => {
                  setSelectedId(id);
                  setEditMode(true);
                } }
                onDeleteClick={handleDeleteItem}
              />
            ))}
          </div>
          <DragOverlay>
            {activeId && state.items && state.items[activeId] ? (
              <KanbanCardContent
              {...state.items[activeId]}
              id={activeId}
              isDragOverlay
              onCardClick={() => {}}
              onEditClick={() => {}}
              onDeleteClick={() => {}}
              />
            ) : null}
          </DragOverlay>
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
                    } }
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
                    confidence_score: state.items[selectedId].confidence_score ?? 0,
                    source_type: state.items[selectedId].source_type,
                    source_value: state.items[selectedId].source_value,
                    due_date: state.items[selectedId].due_date,
                  }}
                  onSave={handleUpdateItem}
                  onDelete={handleDeleteItem}
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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Source Type</label>
                  <select
                      value={newItem.source_type || ''}
                      onChange={(e) => setNewItem({ ...newItem, source_type: e.target.value, source_value: '' })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all bg-white"
                  >
                      <option value="">None</option>
                      <option value="url">URL</option>
                      <option value="directory">Directory</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Due Date</label>
                  <input
                      type="date"
                      value={newItem.due_date || ''}
                      onChange={(e) => setNewItem({ ...newItem, due_date: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                  />
                </div>
                {newItem.source_type && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {newItem.source_type === 'url' ? 'Source URL' : 'Source Directory'}
                    </label>
                    <input
                      type="text"
                      value={newItem.source_value || ''}
                      onChange={(e) => setNewItem({ ...newItem, source_value: e.target.value })}
                      placeholder={newItem.source_type === 'url' ? 'https://example.com' : '/path/to/directory'}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                    />
                  </div>
                )}
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewItem({ id: '', title: '', source_type: '', source_value: '' });
                  }}
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
