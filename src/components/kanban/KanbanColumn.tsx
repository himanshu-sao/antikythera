import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { KanbanCard } from './KanbanCard';
import { STAGE_TITLES } from '../../utils/constants';
import type { KanbanCardData } from '../../types';

interface KanbanColumnProps {
  id: string;
  items: KanbanCardData[];
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
}

export function KanbanColumn({ 
  id, 
  items, 
  onCardClick, 
  onEditClick, 
  onDeleteClick 
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      className={`flex-1 min-w-[220px] bg-[#fbfaf7] rounded-xl border border-[#d8d3ca] p-3 ${
        isOver ? 'bg-[#f1eee8] ring-2 ring-[#0b6b72]' : ''
      }`}
    >
      <div className="flex justify-between items-center mb-3">
        <h2 className="font-bold text-[#231f19] text-xs uppercase tracking-wider">
          {STAGE_TITLES[id] || id}
        </h2>
        <span className="text-[10px] bg-[#ebe7df] text-[#6f6a63] rounded-full px-2 py-0.5 font-medium">
          ({items.length})
        </span>
      </div>
      <div
        ref={setNodeRef}
        className="min-h-[80px]"
      >
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-[#6f6a63] opacity-50 border-2 border-dashed border-gray-200 rounded-xl">
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="24" 
              height="24" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              className="mb-2 opacity-40"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            <p className="text-xs italic">No items in this stage</p>
          </div>
        ) : (
          <SortableContext items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
            {items
              .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
              .map((item) => (
                <KanbanCard
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