import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
}

export function KanbanCard({ id, title, priority, confidence_score, onCardClick }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id,
    data: { id },
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

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
      className={`bg-white p-4 rounded-lg shadow-md cursor-grab hover:shadow-lg transition-all border border-gray-200 mb-3 ${
        isDragging ? 'opacity-50 cursor-grabbing' : ''
      }`}
    >
      <div className="flex justify-between items-start mb-2 gap-2">
        <span className="text-xs font-bold text-gray-500">{id}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${priorityColor}`}>
          {priority}
        </span>
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-2 line-clamp-2">{title}</h3>
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
}

export function KanbanColumn({ id, items, onCardClick }: KanbanColumnProps) {
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
        {items.map((item) => (
          <KanbanCard
            key={item.id}
            id={item.id}
            title={item.title}
            priority={item.priority}
            confidence_score={item.confidence_score}
            onCardClick={onCardClick}
          />
        ))}
      </div>
    </div>
  );
}
