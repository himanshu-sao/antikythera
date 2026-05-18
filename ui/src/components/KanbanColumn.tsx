import React from 'react';
import {
  useSortable,
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { KanbanCardData } from '../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
}

export function KanbanCard({ id, title, priority, confidence_score, onCardClick }: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const priorityColor = {
    High: 'bg-red-100 text-red-800',
    Medium: 'bg-yellow-100 text-yellow-800',
    Low: 'bg-green-100 text-green-800',
  }[priority] || 'bg-gray-100 text-gray-800';

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => onCardClick(id)}
      className="bg-white p-4 rounded-lg shadow-md cursor-grab active:cursor-grabbing hover:shadow-lg transition-all border border-gray-200 mb-3"
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-bold text-gray-500">{id}</span>
        <span className={`text-xs px-2 py-1 rounded-full ${priorityColor}`}>
          {priority}
        </span>
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-2 line-clamp-2">{title}</h3>
      <div className="flex justify-between items-center text-xs text-gray-400">
        <span>Confidence: {confidence_score}%</span>
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
  return (
    <div className="flex-shrink-0 w-72 bg-gray-100 rounded-lg p-4 flex flex-col h-full">
      <h2 className="font-semibold mb-4 text-gray-700 border-b border-gray-300 pb-2">
        {id}
        <span className="ml-2 text-sm font-normal text-gray-500">({items.length})</span>
      </h2>
      <SortableContext
        id={id}
        items={items.map((item) => item.id)}
        strategy={verticalListSortingStrategy}
      >
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
      </SortableContext>
    </div>
  );
}