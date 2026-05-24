import React, { useState, useEffect } from 'react';
import { apiUrl } from '../config';
import { KanbanColumn } from './KanbanColumn';
import toast from 'react-hot-toast';

interface PipelineItem {
  id: string;
  title: string;
  stage: string;
  priority: string;
  source_type: string;
  source_value: string;
}

export function VirtualBoard({ templateId, onBack }: { templateId: string, onBack: () => void }) {
  const [items, setItems] = useState<PipelineItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVirtualBoard();
  }, [templateId]);

  const fetchVirtualBoard = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/boards/virtual/${templateId}`);
      if (!res.ok) throw new Error('Failed to fetch virtual board');
      const data = await res.json();
      setItems(data.items);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const stages = ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"];

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-500">Loading Virtual Board...</div>;

  return (
    <div className="p-6 animate-in fade-in duration-300">
      <div className="flex justify-between items-center mb-6">
        <div>
          <button onClick={onBack} className="text-[#0b6b72] text-sm font-bold hover:underline mb-2 flex items-center gap-1">
            ← Back to Global Pipeline
          </button>
          <h2 className="text-2xl font-bold text-[#231f19]">Virtual Board: {templateId}</h2>
          <p className="text-[#6f6a63] text-sm">Showing only items processed by this workflow template.</p>
        </div>
        <div className="px-3 py-1 bg-[#ebe7df] text-[#6f6a63] rounded-full text-xs font-bold">
          {items.length} items active
        </div>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-6 snap-x">
        {stages.map(stage => (
          <div key={stage} className="flex-shrink-0 w-72 snap-start">
            <KanbanColumn 
              stage={stage} 
              items={items.filter(i => i.stage === stage)} 
            />
          </div>
        ))}
      </div>
    </div>
  );
}
