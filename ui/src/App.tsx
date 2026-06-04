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
import { PipelineDashboard } from './components/PipelineDashboard';
import type { Pipeline, PipelineItem, PipelineState } from './types';
import { apiUrl } from './config';
import { usePipelineState } from './hooks/usePipelineState';
import { CreateItemModal } from './components/modals/CreateItemModal';
import { DeleteConfirmModal } from './components/modals/DeleteConfirmModal';
import { AutomationStudio } from './components/AutomationStudio';
import { WorkflowModal, IntegrationsModal, BuilderModal } from './components/modals/ManagementModals';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

type TabType = 'KANBAN' | 'PIPELINE' | 'STUDIO' | 'WORKFLOWS' | 'INTEGRATIONS';

interface PipelineTab {
  type: 'PIPELINE';
  pipelineId: string;
  pipelineName: string;
}

interface KanbanTab {
  type: 'KANBAN';
}

interface StudioTab {
  type: 'STUDIO';
}

interface WorkflowsTab {
  type: 'WORKFLOWS';
}

interface IntegrationsTab {
  type: 'INTEGRATIONS';
}

type Tab = KanbanTab | PipelineTab | StudioTab | WorkflowsTab | IntegrationsTab;

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
  const [activeTab, setActiveTab] = useState<Tab>({ type: 'KANBAN' });
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [isLoadingPipelines, setIsLoadingPipelines] = useState(false);
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [showStudio, setShowStudio] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [virtualBoardTemplate, setVirtualBoardTemplate] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  // Load pipelines when app starts or when tab changes to a pipeline tab
  useEffect(() => {
    if (activeTab.type === 'PIPELINE' || activeTab.type === 'KANBAN') {
      loadPipelines();
    }
  }, [activeTab]);

  const loadPipelines = async () => {
    setIsLoadingPipelines(true);
    try {
      const res = await fetch(`${apiUrl}/api/pipelines`);
      if (res.ok) {
        const data = await res.json();
        setPipelines(data);
      }
    } catch (e) { console.error("Failed to fetch pipelines", e); }
    finally {
      setIsLoadingPipelines(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { 
        setSelectedId(null); 
        setEditMode(false); 
        setShowCreateModal(false); 
        setShowWorkflow(false); 
        setShowDeleteConfirm(false);
        // Don't close tabs with escape, require explicit close button
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(String(active.id));
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

  // Tab rendering logic
  const renderTabContent = () => {
    if (activeTab.type === 'KANBAN') {
      return renderKanbanBoard();
    } else if (activeTab.type === 'PIPELINE') {
      return renderPipelineTab(activeTab.pipelineId);
    } else if (activeTab.type === 'STUDIO') {
      return <AutomationStudio />;
    } else if (activeTab.type === 'WORKFLOWS') {
      return <div className="p-8 text-center text-gray-500">Workflows section coming soon</div>;
    } else if (activeTab.type === 'INTEGRATIONS') {
      return <div className="p-8 text-center text-gray-500">Integrations section coming soon</div>;
    }
  };

  const renderKanbanBoard = () => {
    if (loading) return <SkeletonBoard />;
    if (error) return <div className="flex items-center justify-center h-screen text-red-500">{error}</div>;

    return (
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
            <KanbanCardContent 
              {...state.items[activeId]} 
              id={activeId} 
              isDragOverlay 
              onCardClick={() => {}} 
              onEditClick={() => {}} 
              onDeleteClick={() => {}}
              blockedReason={state.items[activeId].blocked_reason || undefined}
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    );
  };

  const renderPipelineTab = (pipelineId: string) => {
    return (
      <PipelineDashboard 
        pipelineId={pipelineId} 
        onBack={() => setActiveTab({ type: 'KANBAN' })} 
      />
    );
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Tab Navigation Bar */}
        <div className="bg-white border-b border-[#d8d3ca] shadow-sm">
          <div className="flex items-center px-6 py-3">
            <div className="flex items-center gap-1 overflow-x-auto">
              {/* Kanban Tab */}
              <button
                onClick={() => setActiveTab({ type: 'KANBAN' })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap ${
                  activeTab.type === 'KANBAN'
                    ? 'bg-[#231f19] text-white'
                    : 'text-[#6f6a63] hover:bg-gray-100'
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
                </svg>
                Lifecycle Orchestrator
              </button>

              {/* Studio Tab */}
              <button
                onClick={() => setActiveTab({ type: 'STUDIO' })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap ${
                  activeTab.type === 'STUDIO'
                    ? 'bg-[#231f19] text-white'
                    : 'text-[#6f6a63] hover:bg-gray-100'
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Automation Studio
              </button>

              {/* Workflows Tab */}
              <button
                onClick={() => setActiveTab({ type: 'WORKFLOWS' })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap ${
                  activeTab.type === 'WORKFLOWS'
                    ? 'bg-[#231f19] text-white'
                    : 'text-[#6f6a63] hover:bg-gray-100'
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Workflows
              </button>

              {/* Integrations Tab */}
              <button
                onClick={() => setActiveTab({ type: 'INTEGRATIONS' })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap ${
                  activeTab.type === 'INTEGRATIONS'
                    ? 'bg-[#231f19] text-white'
                    : 'text-[#6f6a63] hover:bg-gray-100'
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
                Integrations
              </button>

              {/* Dynamic Pipeline Tabs */}
              {pipelines.map((pipeline) => (
                <button
                  key={pipeline.pipeline_id}
                  onClick={() => setActiveTab({ type: 'PIPELINE', pipelineId: pipeline.pipeline_id, pipelineName: pipeline.name })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap group relative ${
                    activeTab.type === 'PIPELINE' && activeTab.pipelineId === pipeline.pipeline_id
                      ? 'bg-[#0b6b72] text-white'
                      : 'text-[#6f6a63] hover:bg-gray-100'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                  {pipeline.name}
                  {pipeline.status === 'ACTIVE' && (
                    <span className="w-2 h-2 rounded-full bg-green-400" />
                  )}
                </button>
              ))}

              {/* Add Pipeline Tab Button */}
              <button
                onClick={loadPipelines}
                className="px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1 text-[#0b6b72] hover:bg-[#e0f2f1] whitespace-nowrap"
                title="Refresh pipeline list"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>

            {/* Right-side action buttons */}
            <div className="ml-auto flex gap-2">
              <button 
                onClick={() => setShowCreateModal(true)} 
                className="px-4 py-2 bg-[#0b6b72] text-white rounded-lg text-sm font-medium hover:bg-[#0a5c62] transition-all shadow-sm"
              >
                + New Idea
              </button>
              {activeTab.type === 'KANBAN' && (
                <button 
                  onClick={fetchState} 
                  className="px-4 py-2 bg-white border border-[#d8d3ca] rounded-lg text-sm text-[#6f6a63] hover:bg-gray-50 transition-all"
                >
                  Refresh
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-auto">
          {renderTabContent()}
        </div>

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

        {/* Selected Card Modal */}
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
                    blockedReason: (state.items[selectedId] as any)?.blocked_reason || undefined,
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