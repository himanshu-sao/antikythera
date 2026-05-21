import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
}

export function KanbanCard({ id, title, priority, confidence_score, onCardClick, onEditClick, source_type, source_value }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id,
    data: { id },
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, zIndex: isDragging ? 50 : undefined }
    : { zIndex: isDragging ? 50 : undefined };

  const priorityColor = {
    high: 'bg-red-100 text-red-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
  }[priority?.toLowerCase()] || 'bg-gray-100 text-gray-800';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={() => onCardClick(id)}
      className={`bg-white p-4 rounded-lg shadow-md cursor-grab hover:shadow-lg transition-all border border-gray-200 mb-3 touch-none ${
        isDragging ? 'opacity-50 cursor-grabbing' : ''
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
        </div>
        <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${priorityColor}`}>
          {priority}
        </span>
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-2 line-clamp-2">{title}</h3>
      {source_type && (
        <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
          <span>{source_type === 'url' ? '🌐' : '📁'}</span>
          <span className="truncate" title={source_value}>{source_value}</span>
        </div>
      )}
      <div className="flex justify-between items-center text-xs text-gray-400">
        <span>Confidence: {confidence_score ?? 0}%</span>
      </div>
    </div>
  );
}

interface KanbanColumnProps {
  id: string;
  items: KanbanCardData[];
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
}

export function KanbanColumn({ id, items, onCardClick, onEditClick }: KanbanColumnProps) {
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
      ref={setNodeRef}
      className={`flex-shrink-0 w-72 rounded-lg p-4 flex flex-col h-full border-t-4 transition-colors ${
        borderColor
      } ${isOver ? 'bg-gray-200' : 'bg-gray-100'}`}
    >
      <h2 className="font-semibold mb-4 text-gray-700 border-b border-gray-300 pb-2">
        {stageTitles[id] || id}
        <span className="ml-2 text-sm font-normal text-gray-500">({items.length})</span>
      </h2>
      <div className="flex-1 overflow-y-auto min-h-[100px]">
        {items.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            <p className="text-sm">No items yet</p>
            <p className="text-xs mt-1">Drag cards here</p>
          </div>
        ) : items.map((item) => (
          <KanbanCard
            key={item.id}
            id={item.id}
            title={item.title}
            priority={item.priority}
            confidence_score={item.confidence_score}
            source_type={item.source_type}
            source_value={item.source_value}
            onCardClick={onCardClick}
            onEditClick={onEditClick}
          />
        ))}
      </div>
    </div>
  );
}
