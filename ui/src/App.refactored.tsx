import React, { useState, useEffect, useCallback } from 'react';
import { DndContext, DragOverlay } from '@dnd-kit/core';
import { KanbanColumn } from './kanban/KanbanColumn';
import { ArtifactViewer } from './artifact/ArtifactViewer';
import { SkeletonBoard } from './layout/SkeletonBoard';
import { CardEditor } from './editor/CardEditor';
import { ErrorBoundary } from './layout/ErrorBoundary';
import { CreateItemModal, DeleteConfirmModal } from './modals/ItemModals';
import { WorkflowModal, IntegrationsModal, BuilderModal } from './modals/ManagementModals';
import { usePipelineState } from '../hooks/usePipelineState';
import { useModalManager } from '../hooks/useModalManager';
import { useDragAndDrop } from '../hooks/useDragAndDrop';
import { useSelectedItem } from '../hooks/useSelectedItem';
import { STAGES } from '../utils/constants';
import type { PipelineItem } from '../types';

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

  const {
    showCreateModal,
    showWorkflow,
    showIntegrations,
    showBuilder,
    showDeleteConfirm,
    openCreateModal,
    closeCreateModal,
    openDeleteConfirm,
    closeDeleteConfirm,
    setShowWorkflow,
    setShowIntegrations,
    setShowBuilder,
    setShowDeleteConfirm,
    setDeleteTargetId,
  } = useModalManager();

  const {
    activeId,
    sensors,
    handleDragStart,
    handleDragEnd,
  } = useDragAndDrop();

  const {
    selectedId,
    selectedRunId,
    editMode,
    handleCardClick,
    closeSelectedItem,
    toggleEditMode,
    setSelectedId,
    setSelectedRunId,
    setEditMode,
  } = useSelectedItem();

  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { 
        closeSelectedItem();
        closeCreateModal();
        setShowWorkflow(false);
        setShowIntegrations(false);
        setShowBuilder(false);
        setShowDeleteConfirm(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleDragEndCallback = useCallback((event: any) => {
    handleDragEnd(event, state, handleMoveItem, STAGES);
  }, [state, handleMoveItem, STAGES]);

  if (loading) return <SkeletonBoard />;
  if (error) return <div className="flex items-center justify-center h-screen text-red-500">{error}</div>;

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex flex-col">
            <h1 className="text-3xl font-bold text-[#231f19]">Antikythera Pipeline</h1>
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
              onClick={openCreateModal}
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

        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEndCallback}>
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
                  onCardClick={handleCardClick}
                  onEditClick={(id) => { setSelectedId(id); setEditMode(true); }}
                  onDeleteClick={openDeleteConfirm}
                />
              </div>
            ))}
          </div>
          <DragOverlay>
            {activeId && state.items[activeId] ? (
              <div className="group relative bg-white p-4 rounded-xl shadow-sm cursor-grab hover:shadow-md transition-all border border-[#d8d3ca] mb-3 touch-none shadow-xl ring-2 ring-[#0b6b72] cursor-grabbing">
                <div className="flex flex-wrap gap-1.5 mb-3">
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#d5e7e6] text-[#0b6b72] uppercase tracking-tight">
                    {state.items[activeId].id.split('-')[0]}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#f8ead8] text-[#a45a12] uppercase tracking-tight">
                    {state.items[activeId].priority}
                  </span>
                  {state.items[activeId].confidence_score !== undefined && (
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                      {state.items[activeId].confidence_score}%
                    </span>
                  )}
                </div>
                <h3 className="font-bold text-[#231f19] text-sm mb-1 leading-snug">{state.items[activeId].title}</h3>
                <p className="text-xs text-[#6f6a63] leading-relaxed">
                  {state.items[activeId].source_value || "No description provided."}
                </p>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>

        {/* Modals */}
        <CreateItemModal 
          isOpen={showCreateModal} 
          onClose={closeCreateModal} 
          onCreate={handleCreateItem} 
        />
        <DeleteConfirmModal 
          isOpen={showDeleteConfirm} 
          onClose={closeDeleteConfirm} 
          onConfirm={() => {
            if (deleteTargetId) {
              handleDeleteItem(deleteTargetId);
              closeDeleteConfirm();
            }
          }} 
          targetId={deleteTargetId} 
        />
        <WorkflowModal 
          isOpen={showWorkflow} 
          onClose={() => setShowWorkflow(false)} 
        />
        <IntegrationsModal 
          isOpen={showIntegrations} 
          onClose={() => setShowIntegrations(false)} 
        />
        <BuilderModal 
          isOpen={showBuilder} 
          onClose={() => setShowBuilder(false)} 
        />

        {selectedId && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[90vh] overflow-auto p-6 w-full">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">{selectedId}</h2>
                <div className="flex gap-2 items-center">
                  {!editMode && (
                    <button 
                      onClick={toggleEditMode} 
                      className="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-md text-xs font-medium hover:bg-indigo-100 transition-colors"
                    >
                      Edit Details
                    </button>
                  )}
                  <button 
                    onClick={closeSelectedItem} 
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
                  <ArtifactViewer 
                    itemId={selectedId} 
                    onClose={closeSelectedItem} 
                  />
                </ErrorBoundary>
              )}
            </div>
          </div>
        )}

        <div className="fixed bottom-4 right-4">
          <div className="bg-white rounded-lg shadow-lg p-4 max-w-xs">
            <h3 className="font-bold text-sm mb-2">Filters</h3>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Search..."
                className="w-full px-2 py-1 text-xs border rounded"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <select
                className="w-full px-2 py-1 text-xs border rounded"
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
              >
                <option value="all">All Priorities</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select
                className="w-full px-2 py-1 text-xs border rounded"
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
              >
                <option value="all">All Stages</option>
                {STAGES.map(stage => (
                  <option key={stage} value={stage}>{stage}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}