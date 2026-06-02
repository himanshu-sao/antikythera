import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
  isDragOverlay?: boolean;
  latestStatus?: string;
  blocked_reason?: string;
}

export function KanbanCardContent({
  id,
  title,
  stage,
  priority,
  source_type,
  source_value,
  updated_at,
  confidence_score,
  onCardClick,
  onEditClick,
  onDeleteClick,
  isDragOverlay = false,
  latestStatus,
  blocked_reason,
}: KanbanCardProps) {
  
  const getStatusColor = (val: string) => {
    const v = val?.toLowerCase();
    if (v === 'high' || v === 'needs approval' || v === 'tests failed') return 'bg-[#f8ead8] text-[#a45a12]';
    if (v === 'completed' || v === 'ok') return 'bg-[#dbead8] text-[#2f6b2a]';
    if (v === 'medium' || v === 'low' || v === 'waiting on ci') return 'bg-[#ebe7df] text-[#6f6a63]';
    return 'bg-gray-100 text-gray-600';
  };

  const isError = !!blocked_reason;

  return (
    <div
      onClick={() => onCardClick(id)}
      className={`group relative bg-white p-4 rounded-xl shadow-sm cursor-grab hover:shadow-md transition-all border ${
        isError ? 'border-red-200 bg-red-50/30' : 'border-[#d8d3ca]'
      } mb-3 touch-none ${
        isDragOverlay ? 'shadow-xl ring-2 ring-[#0b6b72] cursor-grabbing' : ''
      }`}
    >
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEditClick(id);
          }}
          className="p-1.5 hover:bg-gray-100 rounded-md text-gray-400 hover:text-[#0b6b72] transition-colors"
          title="Edit"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
          </svg>
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeleteClick(id);
          }}
          className="p-1.5 hover:bg-gray-100 rounded-md text-gray-400 hover:text-red-600 transition-colors"
          title="Delete"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 6h18" />
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
          </svg>
        </button>
      </div>

      {isError && (
        <div className="flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-lg bg-red-100 text-red-700 border border-red-200 animate-pulse mb-2 w-fit max-w-full shadow-sm">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span className="whitespace-normal break-words">Error: {blocked_reason}</span>
        </div>
      )}

      {stage.startsWith('REVIEW_') && !isError && (
        <div className="flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200 animate-pulse mb-2 w-fit max-w-[calc(100%-2.5rem)]">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span className="truncate">ACTION REQUIRED</span>
        </div>
      )}

      {stage === 'EXECUTING' && !isError && (
        <div className="flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full bg-cyan-100 text-cyan-700 border border-cyan-200 animate-pulse mb-2 w-fit max-w-[calc(100%-2.5rem)]">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
          <span className="truncate">{latestStatus || 'AGENT WORKING...'}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#d5e7e6] text-[#0b6b72] uppercase tracking-tight">
          {id.split('-')[0]}
        </span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tight ${getStatusColor(priority)}`}>
          {priority}
        </span>
        {confidence_score !== undefined && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
            {confidence_score}%
          </span>
        )}
      </div>

      <h3 className="font-bold text-[#231f19] text-sm mb-1 leading-snug">{title}</h3>
      <p className="text-xs text-[#6f6a63] leading-relaxed">
        {source_value || "No description provided."}
      </p>

      <div className="mt-3 pt-2 border-t border-gray-50 flex justify-between items-center text-[10px] text-gray-400">
        <div className="flex items-center gap-1">
          <span>{id}</span>
          <span className="mx-1">•</span>
          <span>{updated_at ? new Date(updated_at).toLocaleDateString() : 'N/A'}</span>
        </div>
        {source_type && <span>{source_type === 'url' ? '🌐' : '📄'}</span>}
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
      className={`touch-none ${
        isDragging ? 'opacity-40' : ''
      }`}
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
      className={`touch-none ${
        isDragging ? 'opacity-40' : ''
      }`}
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
  const { setNodeRef, isOver } = useDroppable({ id });

  const stageTitles: Record<string, string> = {
    INTAKE: 'Intake',
    REFINEMENT: 'Refinement',
    REVIEW_SPEC: 'Review Spec',
    ARCHITECTURE: 'Architecture',
    REVIEW_ARCH: 'Review Arch',
    TESTING: 'Testing',
    REVIEW_TEST: 'Review Test',
    APPROVED: 'Approved',
    EXECUTING: 'Executing',
    DONE: 'Done',
  };

  return (
    <div
      className={`flex-1 min-w-[220px] bg-[#fbfaf7] rounded-xl border border-[#d8d3ca] p-3 ${
        isOver ? 'bg-[#f1eee8] ring-2 ring-[#0b6b72]' : ''
      }`}
    >
      <div className="flex justify-between items-center mb-3">
        <h2 className="font-bold text-[#231f19] text-xs uppercase tracking-wider">{stageTitles[id] || id}</h2>
        <span className="text-[10px] bg-[#ebe7df] text-[#6f6a63] rounded-full px-2 py-0.5 font-medium">({items.length})</span>
      </div>
      <div
        ref={setNodeRef}
        className="min-h-[80px]"
      >
        {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-[#6f6a63] opacity-50 border-2 border-dashed border-gray-200 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-2 opacity-40">
                <path d="M12 5v14M5 12h14" />
              </svg>
              <p className="text-xs italic">No items in this stage</p>
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
    </div>
  );
}
