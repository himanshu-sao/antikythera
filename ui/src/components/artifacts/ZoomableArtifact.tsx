import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface ZoomableArtifactProps {
  children: React.ReactNode;
  altText?: string;
}

export const ZoomableArtifact = ({ children, altText = "Artifact Zoom" }: ZoomableArtifactProps) => {
  const [isZoomed, setIsZoomed] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsZoomed(false);
    };
    if (isZoomed) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden'; // Prevent background scroll
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isZoomed]);

  return (
    <>
      <div 
        onClick={() => setIsZoomed(true)}
        className="relative cursor-zoom-in transition-opacity hover:opacity-90 group"
      >
        {children}
        <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/50 text-white text-[10px] px-2 py-1 rounded pointer-events-none">
          Click to zoom
        </div>
      </div>

      {isZoomed && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-sm animate-in fade-in zoom-in-95 duration-200"
          onClick={() => setIsZoomed(false)}
        >
          <button 
            className="absolute top-6 right-6 p-2 bg-white/10 hover:bg-white/20 text-white rounded-full transition-colors"
            onClick={() => setIsZoomed(false)}
          >
            <X className="w-6 h-6" />
          </button>
          
          <div className="max-w-[90vw] max-h-[90vh] p-4 flex items-center justify-center">
            <div className="relative scale-110">
               {children}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
