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
}

export function KanbanCardContent({
  id,
  title,
  stage,
  priority,
  source_type,
  source_value,
  onCardClick,
  onEditClick,
  onDeleteClick,
  isDragOverlay = false,
}: KanbanCardProps) {
  
  // Map priority/status to colors based on mockup
  const getStatusColor = (val: string) => {
    const v = val?.toLowerCase();
    if (v === 'high' || v === 'needs approval' || v === 'tests failed') return 'bg-[#f8ead8] text-[#a45a12]';
    if (v === 'completed' || v === 'ok') return 'bg-[#dbead8] text-[#2f6b2a]';
    if (v === 'medium' || v === 'low' || v === 'waiting on ci') return 'bg-[#ebe7df] text-[#6f6a63]';
    return 'bg-gray-100 text-gray-600';
  };

  return (
    <div
      onClick={() => onCardClick(id)}
      className={`group relative bg-white p-4 rounded-xl shadow-sm cursor-grab hover:shadow-md transition-all border border-[#d8d3ca] mb-3 touch-none ${
        isDragOverlay ? 'shadow-xl ring-2 ring-[#0b6b72] cursor-grabbing' : ''
      }`}
    >
      {/* Action Buttons - hidden by default, show on hover for clean 'Product' look */}
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

      {/* Top Tags */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {/* Workflow Tag - Always Teal */}
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#d5e7e6] text-[#0b6b72] uppercase tracking-tight">
          {id.split('-')[0]} {/* Simplified workflow name from ID */}
        </span>
        {/* Status/Priority Tag */}
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tight ${getStatusColor(priority)}`}>
          {priority}
        </span>
      </div>

      {/* Content */}
      <h3 className="font-bold text-[#231f19] text-sm mb-1 leading-snug">{title}</h3>
      <p className="text-xs text-[#6f6a63] leading-relaxed">
        {source_value || "No description provided."}
      </p>

      {/* Subtle Footer */}
      <div className="mt-3 pt-2 border-t border-gray-50 flex justify-between items-center text-[10px] text-gray-400">
        <span>{id}</span>
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
}

export function KanbanColumn({ id, items, onCardClick, onEditClick, onDeleteClick }: KanbanColumnProps) {
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
          <div className="flex flex-col items-center justify-center py-8 text-[#6f6a63] opacity-50">
            <p className="text-xs">No items yet</p>
          </div>
        ) : (
          <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
            {items
              .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
              .map((item) => (
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