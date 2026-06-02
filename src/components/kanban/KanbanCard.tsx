import React from 'react';
import { useDraggable } from '@dnd-kit/core';
import type { KanbanCardData } from '../../types';

interface KanbanCardProps extends KanbanCardData {
  onCardClick: (id: string) => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
}

export function KanbanCard({
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
  blocked_reason,
}: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: { id },
  });

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
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={() => onCardClick(id)}
      className={`group relative bg-white p-4 rounded-xl shadow-sm cursor-grab hover:shadow-md transition-all border ${
        isError ? 'border-red-200 bg-red-50/30' : 'border-[#d8d3ca]'
      } mb-3 touch-none ${isDragging ? 'opacity-40' : ''}`}
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
          <span className="truncate">AGENT WORKING...</span>
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