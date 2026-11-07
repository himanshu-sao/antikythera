import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

// securityLevel 'strict' keeps diagram text from injecting HTML/JS (mermaid's 'loose' allows
// click handlers and raw HTML labels). Configured once at module load.
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'strict',
});

export const Mermaid = ({ chart, isCodeBlock = false }: { chart: string, isCodeBlock?: boolean }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      const node = containerRef.current;
      const timer = setTimeout(() => {
        mermaid.run({ nodes: [node] }).catch((err: unknown) => {
          console.error('Mermaid render failed', err);
        });
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
