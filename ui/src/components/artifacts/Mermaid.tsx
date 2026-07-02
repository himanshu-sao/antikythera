import React, { useEffect, useRef } from 'react';
let mermaid: any;
try {
  // Dynamically require mermaid; fallback to no‑op stub in test/Jest environment
  mermaid = require('mermaid');
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
  });
} catch {
  // Provide minimal stub with required methods
  mermaid = {
    init: () => {},
    contentLoaded: () => {},
  } as any;
}

export const Mermaid = ({ chart, isCodeBlock = false }: { chart: string, isCodeBlock?: boolean }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      const timer = setTimeout(() => {
        mermaid.contentLoaded();
        mermaid.init(undefined, containerRef.current!);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [chart]);

  return (
    <div className={`flex justify-center my-4 overflow-hidden ${isCodeBlock ? '' : 'mermaid'}`}>
      <div ref={containerRef} className="mermaid">
        {chart}
      </div>
    </div>
  );
};
