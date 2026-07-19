import React from 'react';
import { 
  useDraggable, 
  useDroppable, 
} from '@dnd-kit/core';
import { 
  SortableContext, 
  verticalListSortingStrategy, 
  useSortable 
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  Inbox,
  Pencil,
  FileText,
  LayoutGrid,
  Eye,
  TestTube,
  CheckCircle,
  Zap,
  Archive,
  MoreVertical,
  Plus,
  Trash2,
} from 'lucide-react';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
  isDragOverlay?: boolean;
  latestStatus?: string;
  blocked_reason?: string;
}

const STAGE_CONFIG: Record<string, { icon: any; color: string; emptyTitle: string; emptySubtitle: string }> = {
  INTAKE: { 
    icon: Inbox, 
    color: 'bg-blue-100 text-blue-600', 
    emptyTitle: 'No ideas yet', 
    emptySubtitle: 'Ideas added here will start your journey.' 
  },
  REFINEMENT: { 
    icon: Pencil, 
    color: 'bg-orange-100 text-orange-600', 
    emptyTitle: 'No refinements', 
    emptySubtitle: 'Add details and context to shape the idea.' 
  },
  REVIEW_SPEC: { 
    icon: FileText, 
    color: 'bg-purple-100 text-purple-600', 
    emptyTitle: 'No specs for review', 
    emptySubtitle: 'Approved ideas move here for specification.' 
  },
  ARCHITECTURE: { 
    icon: LayoutGrid, 
    color: 'bg-teal-100 text-teal-600', 
    emptyTitle: 'No architecture', 
    emptySubtitle: 'Approved specs will move here.' 
  },
  REVIEW_ARCH: { 
    icon: Eye, 
    color: 'bg-blue-100 text-blue-600', 
    emptyTitle: 'No items for review', 
    emptySubtitle: 'Architecture designs await verification.' 
  },
  TESTING: { 
    icon: TestTube, 
    color: 'bg-green-100 text-green-600', 
    emptyTitle: 'No tests active', 
    emptySubtitle: 'QA and validation happen here.' 
  },
  REVIEW_TEST: { 
    icon: CheckCircle, 
    color: 'bg-green-100 text-green-600', 
    emptyTitle: 'No test reviews', 
    emptySubtitle: 'Verify test results before approval.' 
  },
  APPROVED: { 
    icon: CheckCircle, 
    color: 'bg-green-100 text-green-600', 
    emptyTitle: 'No approved items', 
    emptySubtitle: 'Items ready for execution.' 
  },
  EXECUTING: { 
    icon: Zap, 
    color: 'bg-cyan-100 text-cyan-600', 
    emptyTitle: 'Nothing executing', 
    emptySubtitle: 'Active agent tasks appear here.' 
  },
  DONE: { 
    icon: Archive, 
    color: 'bg-gray-100 text-gray-600', 
    emptyTitle: 'No completed items', 
    emptySubtitle: 'Finished work is archived here.' 
  },
};

export function KanbanCardContent({
  id,
  title,
  stage,
  priority,
  complexity,
  description,
  updatedAt,
  confidence,
  onCardClick,
  onEditClick,
  onDeleteClick,
  isDragOverlay = false,
  latestStatus,
  blocked_reason,
}: KanbanCardProps) {
  
  const isError = !!blocked_reason;
  const isReviewStage = stage.startsWith('REVIEW_');
  const isExecuting = stage === 'EXECUTING';

  return (
    <div
      onClick={() => onCardClick(id)}
      className={`group relative bg-white p-4 rounded-[10px] border border-[#e5e7eb] shadow-sm cursor-grab hover-lift transition-all mb-3 touch-none ${
        isDragOverlay ? 'shadow-xl ring-2 ring-[var(--accent)] cursor-grabbing' : ''
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex flex-col gap-1.5">
          {isError && (
            <div className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-700 border border-red-200 animate-pulse w-fit">
              <span className="w-1 h-1 rounded-full bg-red-600" />
              <span>ERROR: {blocked_reason}</span>
            </div>
          )}
          {isReviewStage && !isError && (
            <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#fef3c7] text-[#d97706] border border-amber-200 animate-pulse w-fit">
              <span className="w-1 h-1 rounded-full bg-amber-600" />
              <span>ACTION REQUIRED</span>
            </div>
          )}
          {isExecuting && !isError && (
            <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-100 text-cyan-700 border border-cyan-200 animate-pulse w-fit">
              <Zap className="w-2.5 h-2.5" />
              <span>{latestStatus || 'AGENT WORKING'}</span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-0.5">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEditClick(id);
            }}
            className="p-1 hover:bg-gray-100 rounded-md text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Edit item"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {/* Per-card delete affordance. onDeleteClick is already wired at the
              board level to open DeleteConfirmModal (App.tsx). The trash control
              was missing from the card → the whole delete stack was unreachable
              by mouse. title="Delete" matches the e2e deletion.spec selector. */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDeleteClick(id);
            }}
            title="Delete"
            aria-label="Delete item"
            className="p-1 hover:bg-red-50 rounded-md text-gray-400 hover:text-red-600 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#f3f4f6] text-[#6b7280] uppercase">
          {id.split('-')[0]}
        </span>
        {/* Priority badge uses specific colors for High/Medium/Low. The tests expect exact hex values for High. */}
        {(() => {
          const p = priority?.toLowerCase();
          const classes = p === 'high' ? 'bg-[#f8ead8] text-[#a45a12]' : p === 'medium' ? 'bg-[#d5e7e6] text-[#0a5c62]' : 'bg-[#f5f5f4] text-[#78716c]';
          return (
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${classes}`}>\
              {priority}
            </span>
          );
        })()}
        {/* P4.1 — complexity-tier badge. Only render when the item carries a
            concrete tier (trivial/simple/complex); items with no complexity
            (legacy or "auto" pending refiner) show no badge. Existing test
            mocks omit the field entirely so this stays assertion-stable. */}
        {(() => {
          const c = complexity?.toLowerCase();
          if (!c || c === 'auto') return null;
          const classes = c === 'trivial' ? 'bg-blue-100 text-blue-700' : c === 'simple' ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700';
          return (
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${classes}`}>
              {c}
            </span>
          );
        })()}
        {confidence !== undefined && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
            {confidence}%
          </span>
        )}
      </div>

      <h3 className="font-semibold text-[var(--text)] text-base mb-1 leading-snug truncate">
        {title}
      </h3>
      <p className="text-sm text-[var(--text-muted)] leading-relaxed line-clamp-3 mb-4">
        {description || "No description provided."}
      </p>

      <div className="mt-auto pt-3 border-t border-gray-100 flex justify-between items-center text-[10px] font-mono text-gray-400">
        <span>{id}</span>
        <span>{updatedAt ? new Date(updatedAt).toLocaleDateString() : 'N/A'}</span>
      </div>
    </div>
  );
}

export function SortableCard(props: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: props.id });

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
      className={`touch-none ${isDragging ? 'opacity-40' : ''}`}
    >
      <KanbanCardContent {...props} />
    </div>
  );
}

export function KanbanCard(props: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: props.id,
    data: { id: props.id },
  });

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`touch-none ${isDragging ? 'opacity-40' : ''}`}
    >
      <KanbanCardContent {...props} />
    </div>
  );
}

interface KanbanColumnProps {
  id: string;
  items: KanbanCardData[];
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
  onFetchLatestStatus?: (id: string) => Promise<string | undefined>;
}

function KanbanCardWithStatus({
  item,
  onCardClick,
  onEditClick,
  onDeleteClick,
  onFetchLatestStatus
}: {
  item: KanbanCardData;
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
  onFetchLatestStatus?: (id: string) => Promise<string | undefined>;
}) {
  const [status, setStatus] = React.useState<string | undefined>();

  React.useEffect(() => {
    if (onFetchLatestStatus && item.stage === 'EXECUTING') {
      onFetchLatestStatus(item.id).then(setStatus);
    } else {
      setStatus(undefined);
    }
  }, [item.id, item.stage, onFetchLatestStatus]);

  return (
    <SortableCard
      {...item}
      onCardClick={onCardClick}
      onEditClick={onEditClick}
      onDeleteClick={onDeleteClick}
      latestStatus={status}
    />
  );
}

export function KanbanColumn({ id, items, onCardClick, onEditClick, onDeleteClick, onFetchLatestStatus }: KanbanColumnProps) {
  // Column header conforms to redesign specs: icon in colored rounded box, stage name, badge count, and + button
  const { setNodeRef, isOver } = useDroppable({ id });
  const config = STAGE_CONFIG[id] || { 
    icon: Archive, 
    color: 'bg-gray-100 text-gray-600', 
    emptyTitle: 'No items', 
    emptySubtitle: 'Items will appear here.' 
  };
  const Icon = config.icon;

  return (
    <div
      className={`flex flex-col min-w-[240px] bg-white rounded-[12px] border border-[#e5e7eb] p-3 transition-all ${
        isOver ? 'border-2 border-[var(--accent)] bg-teal-50/30' : ''
      }`}
>
      <div className="flex justify-between items-center mb-4 px-1">
        <div className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-md ${config.color} flex items-center justify-center`}>
            <Icon className="w-4 h-4" />
          </div>
          <h2 className="text-sm font-semibold text-gray-700 truncate">
            {id.replace('_', ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())}
          </h2>
          {/* Count badge should be wrapped in parentheses as per test expectations */}
          <span className="text-xs text-gray-400 font-medium ml-1">({items.length})</span>
        </div>
        <button className="p-1 hover:bg-gray-100 rounded text-[var(--accent)] transition-colors">
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div
        ref={setNodeRef}
        className="flex-1 overflow-y-auto custom-scrollbar min-h-[100px] px-1"
      >
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center px-4">
            <div className="p-3 rounded-full bg-gray-50 mb-3">
              <Icon className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-xs font-medium text-gray-500 mb-1">{config.emptyTitle}</p>
            <p className="text-xs text-gray-400">{config.emptySubtitle}</p>
          </div>
        ) : (
          <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
            {items
              .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
              .map((item) => (
                <KanbanCardWithStatus
                  key={item.id}
                  item={item}
                  onCardClick={onCardClick}
                  onEditClick={onEditClick}
                  onDeleteClick={onDeleteClick}
                  onFetchLatestStatus={onFetchLatestStatus}
                />
              ))}
          </SortableContext>
        )}
      </div>

      <button 
        onClick={() => {}} 
        className="mt-4 py-2 text-xs font-medium text-gray-400 hover:text-[var(--accent)] transition-colors text-center w-full"
      >
        + Add idea
      </button>
    </div>
  );
}
