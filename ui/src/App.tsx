import React, { useState, useEffect } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  closestCorners,
} from '@dnd-kit/core';
import { 
  Home, 
  LayoutGrid, 
  PenLine, 
  Workflow, 
  Globe, 
  Cpu, 
  Settings, 
  Plus, 
  RefreshCw, 
  User, 
  ChevronDown,
  X
} from 'lucide-react';
import { KanbanColumn, KanbanCardContent } from './components/KanbanColumn';
import { ArtifactViewer } from './components/ArtifactViewer';
import { SkeletonBoard } from './components/SkeletonBoard';
import { CardEditor } from './components/CardEditor';
import { ErrorBoundary } from './components/ErrorBoundary';
import { VirtualBoard } from './components/VirtualBoard';
import { Toaster } from 'react-hot-toast';
import { PipelineDashboard } from './components/PipelineDashboard';
import { WorkflowManager } from './components/WorkflowManager';
import { IntegrationsManager } from './components/IntegrationsManager';
import type { Pipeline, PipelineState } from './types';
import { apiUrl } from './config';
import { usePipelineState } from './hooks/usePipelineState';
import { CreateItemModal } from './components/modals/CreateItemModal';
import { DeleteConfirmModal } from './components/modals/DeleteConfirmModal';
import { WorkflowGuideModal } from './components/modals/WorkflowGuideModal';
import { AutomationStudio } from './components/AutomationStudio';
import { BuilderModal } from './components/modals/ManagementModals';
import AIEngineSettings from './components/AIEngineSettings';

const STAGES = [
  "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
  "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
];

type TabType = 'KANBAN' | 'PIPELINE' | 'STUDIO' | 'WORKFLOWS' | 'INTEGRATIONS' | 'AI_ENGINE' | 'HOME';

interface Tab {
  type: TabType;
  pipelineId?: string;
  pipelineName?: string;
}

export default function App() {
  const { 
    state, 
    loading, 
    error, 
    handleUpdateItem,
    handleDeleteItem,
    handleCreateItem,
    handleMoveItem,
    handleReorder,
    fetchState
  } = usePipelineState();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>({ type: 'HOME' });
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [isLoadingPipelines, setIsLoadingPipelines] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [showWorkflowGuide, setShowWorkflowGuide] = useState(false);
  const [virtualBoardTemplate, setVirtualBoardTemplate] = useState<string | null>(null);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark';
    const savedCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (savedTheme) setTheme(savedTheme);
    if (savedCollapsed !== null) setIsSidebarCollapsed(savedCollapsed);
  }, []);

  useEffect(() => {
    localStorage.setItem('theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('sidebarCollapsed', String(isSidebarCollapsed));
  }, [isSidebarCollapsed]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  useEffect(() => {
    if (activeTab.type === 'PIPELINE' || activeTab.type === 'KANBAN' || activeTab.type === 'HOME') {
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
        setShowDeleteConfirm(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const handleOpenWorkflowBuilder = () => setShowBuilder(true);
    document.addEventListener('open-workflow-builder', handleOpenWorkflowBuilder);
    return () => document.removeEventListener('open-workflow-builder', handleOpenWorkflowBuilder);
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

    // Intra-column reorder (same stage): persist the new full ordering via the
    // bulk /api/items/reorder endpoint. Cross-stage moves go through /api/move.
    if (activeItem.stage === targetStage) {
      // Build the reordered id list: drop the dragged item, then insert it at
      // targetOrder. This matches the backend's ReorderRequest{stage, ordered_ids}.
      const orderedIds = Object.entries(state.items)
        .map(([id, item]) => ({ ...item, id }))
        .filter(item => item.stage === targetStage)
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map(item => item.id);
      const fromIndex = orderedIds.indexOf(itemId);
      if (fromIndex !== -1) orderedIds.splice(fromIndex, 1);
      orderedIds.splice(Math.min(targetOrder, orderedIds.length), 0, itemId);
      // No-op guard: identical ordering shouldn't fire a network call.
      if (fromIndex === orderedIds.indexOf(itemId)) return;
      await handleReorder(targetStage, orderedIds);
      return;
    }

    if ((activeItem.order ?? 0) === targetOrder) return;
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

  const renderTabContent = () => {
    if (activeTab.type === 'HOME' || activeTab.type === 'KANBAN') {
      return renderKanbanBoard();
    } else if (activeTab.type === 'PIPELINE') {
      return renderPipelineTab(activeTab.pipelineId!);
    } else if (activeTab.type === 'STUDIO') {
      return <AutomationStudio />;
    } else if (activeTab.type === 'WORKFLOWS') {
      return <WorkflowManager />;
    } else if (activeTab.type === 'INTEGRATIONS') {
      return <IntegrationsManager />;
    } else if (activeTab.type === 'AI_ENGINE') {
      return <AIEngineSettings />;
    }
    return null;
  };

  const renderKanbanBoard = () => {
    if (loading) return <SkeletonBoard />;
    if (error) return (
      <div className="flex flex-col items-center justify-center h-screen gap-3 text-red-500">
        <div className="text-lg font-semibold">Error: {error}</div>
        <button
          onClick={() => fetchState()}
          className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
        >
          Retry
        </button>
      </div>
    );

    return (
      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        {/* Filter bar — bound to the existing searchQuery/priorityFilter/stageFilter
            state that already filters the column items below. Restored (was present in
            the original UI then dropped); e2e pipeline.spec "should filter ideas by
            search query, priority, and stage" depends on these controls rendering. */}
        <div className="flex flex-wrap items-center gap-2 px-1 pb-3">
          <input
            type="text"
            placeholder="Search ideas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-1.5 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent)] flex-1 min-w-[200px] max-w-xs"
          />
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
          >
            <option value="all">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
          >
            <option value="all">All Stages</option>
            {STAGES.map(stage => (
              <option key={stage} value={stage}>
                {stage.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
          {/* Workflow guide affordance (P3.8.4/#3). Was only on the workflow
              view (WorkflowDiagram.tsx); re-added to the board so the e2e
              pipeline.spec "should open and close workflow guide" has a target. */}
          <button
            onClick={() => setShowWorkflowGuide(true)}
            className="px-3 py-1.5 text-sm font-medium text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--panel-2)] rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <span>ℹ️</span> How it works
          </button>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4 snap-x h-full custom-scrollbar">
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
                onCardClick={(id) => handleCardClick(id)}
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
    return <PipelineDashboard pipelineId={pipelineId} onBack={() => setActiveTab({ type: 'HOME' })} />;
  };

  const navItems = [
    { id: 'HOME', label: 'Home', icon: Home },
    { id: 'KANBAN', label: 'Orchestrator', icon: LayoutGrid },
    { id: 'STUDIO', label: 'Studio', icon: PenLine },
    { id: 'WORKFLOWS', label: 'Workflows', icon: Workflow },
    { id: 'INTEGRATIONS', label: 'Integrations', icon: Globe },
    { id: 'AI_ENGINE', label: 'AI Engine', icon: Cpu },
    { id: 'SETTINGS', label: 'Settings', icon: Settings },
  ];

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-[var(--bg)] flex text-[var(--text)]">
        {/* Left Sidebar */}
        <aside 
          className={`bg-white border-r border-[var(--border)] flex flex-col transition-all duration-200 ease-in-out z-30 ${isSidebarCollapsed ? 'w-[var(--sidebar-collapsed-w)]' : 'w-[var(--sidebar-w)]'}`}
        >
          <div className="p-4 flex items-center gap-3 mb-6">
            <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-white font-bold flex-shrink-0">C</div>
            {!isSidebarCollapsed && <span className="font-semibold text-base truncate">Antikythera</span>}
          </div>

          <nav className="flex-1 px-3 space-y-1">
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => setActiveTab({ type: item.id as TabType })}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab.type === item.id 
                    ? 'bg-[var(--accent-light)] text-[var(--accent)]' 
                    : 'text-[var(--text-muted)] hover:bg-[var(--panel-2)]'
                }`}
              >
                <item.icon className={`w-[18px] h-[18px] ${activeTab.type === item.id ? 'text-[var(--accent)]' : 'text-gray-400'}`} />
                {!isSidebarCollapsed && <span>{item.label}</span>}
              </button>
            ))}
          </nav>

          <div className="p-3 border-t border-[var(--border)]">
            <button className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-[var(--panel-2)] transition-all text-left">
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden flex-shrink-0">
                <User className="w-5 h-5 text-gray-500" />
              </div>
              {!isSidebarCollapsed && (
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">Acme Corp</div>
                  <div className="text-xs text-[var(--text-muted)] truncate">Enterprise</div>
                </div>
              )}
              {!isSidebarCollapsed && <ChevronDown className="w-4 h-4 text-gray-400" />}
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Top Navigation Bar */}
          <header className="h-[52px] bg-white border-b border-[var(--border)] flex items-center px-6 justify-between z-20">
            <div className="flex items-center gap-1 overflow-x-auto custom-scrollbar">
              {navItems.filter(n => n.id !== 'HOME' && n.id !== 'SETTINGS').map(item => (
                <button
                  key={item.id}
                  onClick={() => setActiveTab({ type: item.id as TabType })}
                  className={`px-3 py-1 text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap border-b-2 ${
                    activeTab.type === item.id 
                      ? 'text-[var(--accent)] border-[var(--accent)]' 
                      : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </button>
              ))}
              {pipelines.map(pipeline => (
                <button
                  key={pipeline.pipeline_id}
                  onClick={() => setActiveTab({ type: 'PIPELINE', pipelineId: pipeline.pipeline_id, pipelineName: pipeline.name })}
                  className={`px-3 py-1 text-sm font-medium transition-all flex items-center gap-2 whitespace-nowrap border-b-2 ${
                    activeTab.type === 'PIPELINE' && activeTab.pipelineId === pipeline.pipeline_id
                      ? 'text-[var(--accent)] border-[var(--accent)]' 
                      : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
                  }`}
                >
                  <LayoutGrid className="w-4 h-4" />
                  {pipeline.name}
                  {pipeline.status === 'ACTIVE' && <span className="w-2 h-2 rounded-full bg-green-400" />}
                </button>
              ))}
              <button 
                onClick={loadPipelines}
                className="p-1 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
                title="Refresh pipelines"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <button 
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                className="p-2 rounded-lg hover:bg-[var(--panel-2)] text-[var(--text-muted)] transition-colors"
              >
                {theme === 'light' ? '🌙' : '☀️'}
              </button>
              <button 
                onClick={() => setShowCreateModal(true)} 
                className="px-4 py-1.5 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--accent-hover)] transition-all shadow-sm flex items-center gap-2"
              >
                <Plus className="w-4 h-4" /> New Idea
              </button>
              <div className="w-8 h-8 rounded-full bg-gray-200 border border-[var(--border)] overflow-hidden">
                <img src="https://ui-avatars.com/api/?name=Acme+Corp&background=random" alt="Avatar" />
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-auto p-6 custom-scrollbar relative">
            {renderTabContent()}
          </main>

          {/* Right-side Slide-in Drawer for Card Details */}
          {selectedId && (
            <>
              <div 
                className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity" 
                onClick={() => { setSelectedId(null); setEditMode(false); }} 
              />
              <div className="fixed right-0 top-0 h-full w-full max-w-[520px] bg-white shadow-2xl z-50 transition-transform duration-250 ease-in-out transform translate-x-0 flex flex-col">
                <div className="flex justify-between items-center p-6 border-b border-[var(--border)]">
                  <h2 className="text-xl font-bold truncate pr-4">{selectedId}</h2>
                  <div className="flex gap-2 items-center">
                    {!editMode && (
                      <button 
                        onClick={() => setEditMode(true)} 
                        className="px-3 py-1 bg-[var(--accent-light)] text-[var(--accent)] rounded-md text-xs font-medium hover:opacity-80 transition-all"
                      >
                        Edit Details
                      </button>
                    )}
                    <button 
                      onClick={() => { setSelectedId(null); setEditMode(false); }} 
                      className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-400 hover:text-gray-600"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-6 custom-scrollbar">
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
            </>
          )}

          {virtualBoardTemplate && (
            <div className="fixed inset-0 bg-white z-50 overflow-auto">
              <VirtualBoard 
                templateId={virtualBoardTemplate} 
                onBack={() => setVirtualBoardTemplate(null)} 
              />
            </div>
          )}

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
          <WorkflowGuideModal
            isOpen={showWorkflowGuide}
            onClose={() => setShowWorkflowGuide(false)}
          />
          <BuilderModal
            isOpen={showBuilder} 
            onClose={() => setShowBuilder(false)} 
            itemId={selectedId} 
          />
          <Toaster position="top-right" />
        </div>
      </div>
    </ErrorBoundary>
  );
}
