import React, { useState, useEffect } from 'react';
import { Terminal, CheckCircle2, AlertCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { apiUrl } from "../../config";

interface TimelineEvent {
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  agent: string;
  action: string;
  message: string;
  metadata?: any;
}

export const Timeline = ({ itemId }: { itemId: string }) => {
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchTimeline = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}/timeline`);
      if (res.ok) {
        const data = await res.json();
        setTimeline(data);
      }
    } catch (e) {
      console.error('Failed to fetch timeline', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTimeline();
  }, [itemId]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'text-red-600 bg-red-50 border-red-100';
      case 'WARN': return 'text-amber-600 bg-amber-50 border-amber-100';
      default: return 'text-blue-600 bg-blue-50 border-blue-100';
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'ERROR': return <AlertCircle size={14} />;
      case 'WARN': return <Info size={14} />;
      default: return <CheckCircle2 size={14} />;
    }
  };

  if (loading) return null;
  if (timeline.length === 0) return null;

  return (
    <div className="mt-6 border-t border-gray-200 pt-4">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
      >
        <Terminal size={16} />
        Execution Timeline ({timeline.length} events)
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {isOpen && (
        <div className="mt-4 space-y-4 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
          {timeline.map((event, idx) => (
            <div key={idx} className="relative pl-6 before:content-[''] before:absolute before:left-[7px] before:top-[18px] before:bottom-[-16px] before:w-[2px] before:bg-gray-200 last:before:hidden">
              <div className={`absolute left-0 top-1 w-4 h-4 rounded-full border-2 border-white ring-2 ring-gray-100 flex items-center justify-center ${getLevelColor(event.level).split(' ')[0]}`}>
                {React.cloneElement(getLevelIcon(event.level) as React.ReactElement, { size: 10 })}
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase text-gray-500">{event.agent}</span>
                  <span className="text-[10px] text-gray-400">{new Date(event.timestamp).toLocaleTimeString()}</span>
                </div>
                <div className={`mt-1 text-xs p-2 rounded-md border ${getLevelColor(event.level)}`}>
                  <div className="font-semibold">{event.action}</div>
                  <div className="opacity-90">{event.message}</div>
                  {event.metadata && Object.entries(event.metadata).map(([k, v]) => (
                    <div key={k} className="text-[10px] opacity-70">{k}: {JSON.stringify(v)}</div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
