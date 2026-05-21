import React from 'react';
import { useDraggable, useDroppable, useSortable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
  isDragOverlay?: boolean;
}

// Pure display component used both inline and in DragOverlay
export function KanbanCardContent({
  id,
  title,
  priority,
  confidence_score,
  source_type,
  source_value,
  updated_at,
  due_date,
  onCardClick,
  onEditClick,
  onDeleteClick,
  isDragOverlay = false,
}: KanbanCardProps) {
  const priorityColor = {
    high: 'bg-red-100 text-red-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
  }[priority?.toLowerCase()] || 'bg-gray-100 text-gray-800';

  return (
    <div
      onClick={() => onCardClick(id)}
      className={`bg-white p-4 rounded-lg shadow-md cursor-grab hover:shadow-lg transition-all border border-gray-200 mb-3 touch-none ${
        isDragOverlay ? 'shadow-xl ring-2 ring-indigo-400 cursor-grabbing' : ''
      }`}
    >
      <div className="flex justify-between items-start mb-2 gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-500">{id}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEditClick(id);
            }}
            className="p-1 hover:bg-gray-100 rounded-md text-gray-400 hover:text-indigo-600 transition-colors"
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
            className="p-1 hover:bg-gray-100 rounded-md text-gray-400 hover:text-red-600 transition-colors"
            title="Delete"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${priorityColor}`}>
          {priority}
        </span>
      </div>
      <h3 className="font-semibold text-gray-800 text-sm mb-2">{title}</h3>
      {source_type && (
        <div className="text-xs text-gray-500 mb-1 truncate">
          <span>{source_type === 'url' ? '🌐' : '📄'}</span>
          &nbsp;
          <span>{source_value}</span>
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-gray-400 mt-2">
        <span>Confidence: {confidence_score ?? 0}%</span>
        {due_date && (
          <span className="flex items-center gap-1">
            <span>📅</span>
            <span>{due_date}</span>
          </span>
        )}
        {updated_at && (
          <span className="flex items-center gap-1">
            <span>🕒</span>
            <span>{new Date(updated_at).toLocaleDateString()}</span>
          </span>
        )}
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
}

export function KanbanColumn({ id, items, onCardClick, onEditClick, onDeleteClick }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id });

  const stageColors: Record<string, string> = {
    INTAKE: 'border-t-blue-500',
    REFINEMENT: 'border-t-cyan-500',
    REVIEW_SPEC: 'border-t-indigo-500',
    ARCHITECTURE: 'border-t-purple-500',
    REVIEW_ARCH: 'border-t-fuchsia-500',
    TESTING: 'border-t-pink-500',
    REVIEW_TEST: 'border-t-rose-500',
    APPROVED: 'border-t-orange-500',
    EXECUTING: 'border-t-yellow-500',
    DONE: 'border-t-green-500',
  };

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

  const borderColor = stageColors[id] || 'border-t-gray-500';

  return (
    <div
      className={`flex-1 min-w-[220px] bg-gray-50 rounded-xl border-t-4 ${borderColor} p-3 ${
        isOver ? 'bg-indigo-50 ring-2 ring-indigo-300' : ''
      }`}
    >
      <div className="flex justify-between items-center mb-3">
        <h2 className="font-semibold text-gray-700 text-sm">{stageTitles[id] || id}</h2>
        <span className="text-xs bg-gray-200 text-gray-600 rounded-full px-2 py-0.5">({items.length})</span>
      </div>
      <div
        ref={setNodeRef}
        className="min-h-[80px]"
      >
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <p className="text-sm">No items yet</p>
            <p className="text-xs">Drag cards here</p>
          </div>
        ) : (
          <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
            {items.map((item) => (
              <SortableCard
                key={item.id}
                {...item}
                onCardClick={onCardClick}
                onEditClick={onEditClick}
                onDeleteClick={onDeleteClick}
              />
            ))}
          </SortableContext>
        )}
      </div>
    </div>
  );
}
