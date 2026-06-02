import React, { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, DragStartEvent, PointerSensor, useSensor, useSensors, DragOverlay } from '@dnd-kit/core';
import { KanbanColumn, KanbanCardContent } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import { WorkflowDiagram } from './components/WorkflowDiagram';
import { SkeletonBoard } from './components/SkeletonBoard';
import { CardEditor } from './components/CardEditor';
import { ErrorBoundary } from './components/ErrorBoundary';
import { VirtualBoard } from './components/VirtualBoard';
import { Toaster } from 'react-hot-toast';
import type { PipelineItem, PipelineState } from './types';
import { apiUrl } from './config';

import { usePipelineState } from './hooks/usePipelineState';
import { CreateItemModal } from './components/modals/CreateItemModal';
import { DeleteConfirmModal } from './components/modals/DeleteConfirmModal';
import { WorkflowModal, IntegrationsModal, BuilderModal } from './components/modals/ManagementModals';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

export default function App() {
  const { 
    state, 
    loading, 
    error, 
    handleUpdateItem, 
    handleDeleteItem, 
    handleCreateItem, 
    handleMoveItem,
    fetchState
  } = usePipelineState();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);
  const [virtualBoardTemplate, setVirtualBoardTemplate] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { 
        setSelectedId(null); 
        setEditMode(false); 
        setShowCreateModal(false); 
        setShowWorkflow(false); 
        setShowDeleteConfirm(false); 
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

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
      targetOrder = overIndex === -1 ? columnItems.length : overIndex;
    }

    if (activeItem.stage === targetStage && (activeItem.order ?? 0) === targetOrder) return;
    await handleMoveItem(itemId, targetStage, targetOrder);
  };

  const handleCardClick = async (id: string) => {
    setSelectedId(id);
    setEditMode(false);
    try {
      const res = await fetch(`${apiUrl}/api/workflows/items/${id}/run`);
      if (res.ok) {
        const data = await res.json();
        if (data.run_id) setSelectedRunId(data.run_id);
      }
    } catch (e) { console.error("Failed to check workflow binding", e); }
  };

  if (loading) return <SkeletonBoard />;
  if (error) return <div className="flex items-center justify-center h-screen text-red-500">{error}</div>;

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex flex-col">
            <h1 className="text-3xl font-bold text-[#231f19]">Antikythera Pipeline <span className="text-xs text-gray-400 font-mono ml-2">v1.0.0</span></h1>
            <p className="text-sm text-[#6f6a63]">Generic pipeline + workflow templates</p>
          </div>
          <div className="ml-auto flex gap-2">
            <button 
              onClick={() => setShowWorkflow(true)} 
              className={`px-4 py-2 rounded-full text-sm transition-all border ${showWorkflow ? 'bg-[#231f19] text-white border-[#231f19]' : 'bg-white text-[#6f6a63] border-[#d8d3ca] hover:border-[#231f19]'}`}
            >
              Workflows
            </button>
            <button 
              onClick={() => setShowBuilder(true)} 
              className={`px-4 py-2 rounded-full text-sm transition-all border ${showBuilder ? 'bg-[#231f19] text-white border-[#231f19]' : 'bg-white text-[#6f6a63] border-[#d8d3ca] hover:border-[#231f19]'}`}
            >
              Architect
            </button>
            <button 
              onClick={() => setShowIntegrations(true)} 
              className={`px-4 py-2 rounded-full text-sm transition-all border ${showIntegrations ? 'bg-[#231f19] text-white border-[#231f19]' : 'bg-white text-[#6f6a63] border-[#d8d3ca] hover:border-[#231f19]'}`}
            >
              Integrations
            </button>
            <button 
              onClick={() => setShowCreateModal(true)} 
              className="px-4 py-2 bg-[#0b6b72] text-white rounded-full text-sm font-medium hover:bg-[#0a5c62] transition-all shadow-sm"
            >
              + New Idea
            </button>
            <button 
              onClick={fetchState} 
              className="px-4 py-2 bg-white border border-[#d8d3ca] rounded-full text-sm text-[#6f6a63] hover:bg-gray-50 transition-all"
            >
              Refresh
            </button>
          </div>
        </div>

        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x">
            {STAGES.map(stage => (
              <div key={stage} className="flex-shrink-0 snap-start">
                <KanbanColumn
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
              </div>
            ))}
          </div>
          <DragOverlay>
            {activeId && state.items[activeId] ? (
              <KanbanCardContent {...state.items[activeId]} id={activeId} isDragOverlay onCardClick={() => {}} onEditClick={() => {}} onDeleteClick={() => {}} />
            ) : null}
          </DragOverlay>
        </DndContext>

        {/* Modals */}
        <CreateItemModal 
          isOpen={showCreateModal} 
          onClose={() => setShowCreateModal(false)} 
          onCreate={handleCreateItem} 
        />
        <DeleteConfirmModal 
          isOpen={showDeleteConfirm} 
          onClose={() => setShowDeleteConfirm(false)} 
          onConfirm={() => {
            if (deleteTargetId) {
              handleDeleteItem(deleteTargetId);
              setShowDeleteConfirm(false);
            }
          }} 
          targetId={deleteTargetId} 
        />
        <WorkflowModal isOpen={showWorkflow} onClose={() => setShowWorkflow(false)} />
        <IntegrationsModal isOpen={showIntegrations} onClose={() => setShowIntegrations(false)} />
        <BuilderModal 
          isOpen={showBuilder} 
          onClose={() => setShowBuilder(false)} 
          itemId={selectedId} 
        />

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
                    description: (state.items[selectedId] as any)?.description || '',
                    priority: state.items[selectedId]?.priority || 'medium',
                    confidence_score: state.items[selectedId]?.confidence_score ?? 0,
                    source_type: state.items[selectedId]?.source_type || 'directory',
                    source_value: state.items[selectedId]?.source_value || '',
                    due_date: state.items[selectedId]?.due_date || '',
                  }}
                  onSave={(updates) => handleUpdateItem(selectedId, updates)}
                  onDelete={() => handleDeleteItem(selectedId)}
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

        {virtualBoardTemplate && (
          <div className="fixed inset-0 bg-white z-50 overflow-auto">
            <VirtualBoard 
              templateId={virtualBoardTemplate} 
              onBack={() => setVirtualBoardTemplate(null)} 
            />
          </div>
        )}

        <Toaster position="top-right" />
      </div>
    </ErrorBoundary>
  );
}
