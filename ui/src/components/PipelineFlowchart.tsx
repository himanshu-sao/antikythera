import React from 'react';
import { Path, PathStep } from '../types/legacy-pipeline';

interface FlowNode {
  id: string;
  label: string;
  type: string;
  adapter: string;
  x: number;
  y: number;
}

interface FlowEdge {
  id: string;
  source: string;
  target: string;
}

export function PipelineFlowchart({ paths }: { paths: Path[] }) {
  // We will generate a simple layout since we aren't using a heavy graph library
  // Each path is a vertical column, and we can link paths if they are sequential
  
  return (
    <div className="relative w-full h-full min-h-[600px] bg-[#fcfbf8] rounded-2xl border border-[#d8d3ca] overflow-auto p-10">
      <div className="flex gap-20 items-start justify-center">
        {paths.map((path, pathIdx) => (
          <div key={path.path_id} className="flex flex-col items-center gap-6">
            <div className="px-3 py-1 bg-[#231f19] text-white text-[10px] font-bold rounded-full uppercase tracking-wider mb-2">
              {path.name}
            </div>
            
            <div className="flex flex-col items-center gap-8 relative">
              {path.steps.map((step, stepIdx) => (
                <React.Fragment key={step.step_id}>
                  <div className="group relative z-10">
                    <div className="w-48 p-3 bg-white border-2 border-[#d8d3ca] rounded-xl shadow-sm hover:border-[#0b6b72] transition-all cursor-pointer">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] font-bold text-gray-400 uppercase">Step {stepIdx + 1}</span>
                        <span className="text-[9px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded font-mono">
                          {step.adapter_id.replace('_adapter', '')}
                        </span>
                      </div>
                      <div className="text-xs font-bold text-gray-800 truncate">
                        {step.operator_id.replace('_', ' ')}
                      </div>
                    </div>
                    
                    {/* Tooltip for config */}
                    <div className="absolute left-full ml-4 top-0 w-48 p-2 bg-gray-900 text-white text-[10px] rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                      <div className="font-bold mb-1 text-teal-400">Configuration:</div>
                      <pre className="font-mono whitespace-pre-wrap">
                        {JSON.stringify(step.config, null, 2)}
                      </pre>
                    </div>
                  </div>
                  
                  {stepIdx < path.steps.length - 1 && (
                    <div className="w-0.5 h-8 bg-[#d8d3ca] relative">
                      <div className="absolute bottom-0 left-[-3px] w-2 h-2 rounded-full bg-[#d8d3ca]" />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}
      </div>
      
      {paths.length === 0 && (
        <div className="h-full flex items-center justify-center text-gray-400 italic text-sm">
          No paths defined for this pipeline.
        </div>
      )}
    </div>
  );
}
