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
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');

  // MODAL STATES
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // CREATE ITEM STATE
  const [newItem, setNewItem] = useState({ 
    id: '', 
    title: '', 
    priority: 'medium',
    source_type: 'directory', 
    source_value: '', 
    due_date: '' 
  });

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
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
      if (document.visibilityState === 'hidden') clearInterval(interval);
      else { fetchState(); clearInterval(interval); interval = setInterval(fetchState, 10000); }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setSelectedId(null); setEditMode(false); setShowCreateModal(false); setShowWorkflow(false); setShowDeleteConfirm(false); }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedId]);

  const handleDragStart = (event: DragStartEvent) => setActiveId(String(event.active.id));

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
      targetOrder = overIndex === -1 ? columnItems.length : overIndex;
    }

    if (activeItem.stage === targetStage && (activeItem.order ?? 0) === targetOrder) return;

    try {
      const res = await fetch(`${apiUrl}/api/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, new_stage: targetStage, order: targetOrder }),
      });
      if (res.ok) {
        await fetchState();
      }
    } catch (e) { console.error("Failed to move item", e); }
  };

  const handleUpdateItem = async (updates: any) => {
    if (!selectedId) return;
    try {
      const res = await fetch(`${apiUrl}/api/item/${selectedId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error('Failed to update item');
      await fetchState();
    } catch (e: any) { toast.error(e.message); }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete item');
      setSelectedId(null);
      setShowDeleteConfirm(false);
      await fetchState();
      toast.success("Item deleted");
    } catch (e: any) { toast.error(e.message); }
  };

  const confirmDelete = () => {
    if (deleteTargetId) handleDeleteItem(deleteTargetId);
  };

  const handleCreateItem = async () => {
    if (!newItem.id || !newItem.title) return;
    const itemId = newItem.id.toUpperCase();
    try {
      const res = await fetch(`${apiUrl}/api/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemId,
          title: newItem.title,
          priority: newItem.priority,
          source_type: newItem.source_type,
          source_value: newItem.source_value,
          due_date: newItem.due_date,
        }),
      });
      if (!res.ok) throw new Error('Failed to create item');
      setShowCreateModal(false);
      setNewItem({ id: '', title: '', priority: 'medium', source_type: 'directory', source_value: '', due_date: '' });
      await fetchState();
      toast.success("New idea created");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (error) return <div className="flex items-center justify-center h-screen text-red-500">{error}</div>;

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50 p-6">
        <header className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Hermes Pipeline</h1>
          <div className="mt-4 flex flex-wrap gap-2 items-center justify-between">
            <div className="flex gap-2">
              <button onClick={() => setShowWorkflow(true)} className="px-4 py-2 bg-white border rounded-lg text-sm">Workflow</button>
              <button onClick={() => setShowCreateModal(true)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm">+ New Idea</button>
              <button onClick={fetchState} className="px-4 py-2 bg-white border rounded-lg text-sm">Refresh</button>
            </div>
            <div className="flex gap-2">
              <select value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)} className="p-2 border rounded-lg text-sm">
                <option value="all">All Priorities</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select value={stageFilter} onChange={e => setStageFilter(e.target.value)} className="p-2 border rounded-lg text-sm">
                <option value="all">All Stages</option>
                {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <input type="text" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="p-2 border rounded-lg text-sm" />
            </div>
          </div>
        </header>

        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="grid grid-cols-5 gap-4 overflow-x-auto pb-4">
            {STAGES.map(stage => (
              <KanbanColumn
                key={stage}
                id={stage}
                items={Object.entries(state.items)
                  .filter(([_, item]) => item.stage === stage)
                  .filter(([_, item]) => {
                    const mSearch = !searchQuery || item.id.toLowerCase().includes(searchQuery.toLowerCase()) || item.title.toLowerCase().includes(searchQuery.toLowerCase());
                    const mPri = priorityFilter === 'all' || item.priority?.toLowerCase() === priorityFilter;
                    const mStage = stageFilter === 'all' || item.stage === stageFilter;
                    return mSearch && mPri && mStage;
                  })
                  .map(([id, item]) => ({ ...item, id }))
                  .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))}
                onCardClick={(id) => { setSelectedId(id); setEditMode(false); }}
                onEditClick={(id) => { setSelectedId(id); setEditMode(true); }}
                onDeleteClick={(id) => { setDeleteTargetId(id); setShowDeleteConfirm(true); }}
              />
            ))}
          </div>
          <DragOverlay>
            {activeId && state.items[activeId] ? (
              <KanbanCardContent {...state.items[activeId]} id={activeId} isDragOverlay onCardClick={() => {}} onEditClick={() => {}} onDeleteClick={() => {}} />
            ) : null}
          </DragOverlay>
        </DndContext>

        {/* CREATE MODAL */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h2 className="text-xl font-bold mb-4">Create New Idea</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Item ID</label>
                  <input type="text" className="w-full p-2 border rounded" value={newItem.id} onChange={e => setNewItem({...newItem, id: e.target.value})} placeholder="e.g. IDEA-1" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Title</label>
                  <input type="text" className="w-full p-2 border rounded" value={newItem.title} onChange={e => setNewItem({...newItem, title: e.target.value})} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Priority</label>
                  <select className="w-full p-2 border rounded" value={newItem.priority} onChange={e => setNewItem({...newItem, priority: e.target.value})}>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Source Type</label>
                  <select className="w-full p-2 border rounded" value={newItem.source_type} onChange={e => setNewItem({...newItem, source_type: e.target.value})}>
                    <option value="directory">Directory (Local File)</option>
                    <option value="url">URL (Web Link)</option>
                    <option value="text">Direct Text</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Source Value (Path/URL/Text)</label>
                  <input type="text" className="w-full p-2 border rounded" value={newItem.source_value} onChange={e => setNewItem({...newItem, source_value: e.target.value})} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Due Date</label>
                  <input type="date" className="w-full p-2 border rounded" value={newItem.due_date} onChange={e => setNewItem({...newItem, due_date: e.target.value})} />
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <button onClick={() => setShowCreateModal(false)} className="px-4 py-2 text-gray-600">Cancel</button>
                  <button onClick={handleCreateItem} className="px-4 py-2 bg-indigo-600 text-white rounded-lg">Create</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* DELETE CONFIRM MODAL */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-[60]">
            <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6">
              <h2 className="text-xl font-bold text-red-600 mb-2">Delete Item?</h2>
              <p className="text-gray-600 mb-6">Are you sure you want to delete <span className="font-bold">{deleteTargetId}</span>? This cannot be undone.</p>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowDeleteConfirm(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
                <button onClick={confirmDelete} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">Delete</button>
              </div>
            </div>
          </div>
        )}

        {/* DETAIL MODAL (EDITOR / VIEWER) */}
        {selectedId && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto p-6 w-full">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">{selectedId}</h2>
                <div className="flex gap-2 items-center">
                  {!editMode && (
                    <button onClick={() => setEditMode(true)} className="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-md text-xs font-medium hover:bg-indigo-100 transition-colors">
                      Edit Details
                    </button>
                  )}
                  <button onClick={() => { setSelectedId(null); setEditMode(false); }} className="p-2 hover:bg-gray-100 rounded-full transition-colors">✕</button>
                </div>
              </div>
              {editMode ? (
                <CardEditor
                  itemId={selectedId}
                  initialData={{
                    title: state.items[selectedId]?.title || '',
                    description: state.items[selectedId]?.description || '',
                    priority: state.items[selectedId]?.priority || 'medium',
                    confidence_score: state.items[selectedId]?.confidence_score ?? 0,
                    source_type: state.items[selectedId]?.source_type || 'directory',
                    source_value: state.items[selectedId]?.source_value || '',
                    due_date: state.items[selectedId]?.due_date || '',
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

        {showWorkflow && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">Workflow Guide</h2>
                <button onClick={() => setShowWorkflow(false)} className="p-2 hover:bg-gray-100 rounded-full transition-colors">✕</button>
              </div>
              <WorkflowDiagram onClose={() => setShowWorkflow(false)} />
            </div>
          </div>
        )}

        <Toaster position="top-right" />
      </div>
    </ErrorBoundary>
  );
}
