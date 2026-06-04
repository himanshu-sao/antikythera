import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

interface HighlighterProps {
  text: string;
  onExtract: (selectedText: string) => void;
}

export function TextHighlighter({ text, onExtract }: HighlighterProps) {
  const [selectedText, setSelectedText] = useState<string>('');

  const handleMouseUp = () => {
    const selection = window.getSelection()?.toString();
    if (selection && selection.trim()) {
      setSelectedText(selection.trim());
    }
  };

  return (
    <div className="relative group">
      <div 
        onMouseUp={handleMouseUp}
        className="p-4 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 leading-relaxed whitespace-pre-wrap cursor-text"
      >
        {text}
      </div>
      
      {selectedText && (
        <div className="absolute top-2 right-2 z-10 animate-in fade-in zoom-in-95">
          <button 
            onClick={() => {
              onExtract(selectedText);
              setSelectedText('');
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-[#0b6b72] text-white rounded-lg text-[10px] font-bold shadow-lg hover:bg-[#0a5c62] transition-all"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
            Extract as Field
          </button>
        </div>
      )}
    </div>
  );
}
