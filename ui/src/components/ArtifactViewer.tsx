import React, { useState, useEffect, useRef } from 'react';
import { debounce } from 'lodash';
import { apiUrl } from '../config';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';
import { Clock, CheckCircle2, AlertCircle, Info, ChevronDown, ChevronUp, Terminal, FileText, CheckSquare } from 'lucide-react';

// Initialize mermaid
mermaid.initialize({ 
  startOnLoad: false, 
  theme: 'dark',
  securityLevel: 'loose' 
});

// Component to handle mermaid rendering within markdown code blocks
const MermaidCodeBlock = ({ code }: { code: string }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      const timer = setTimeout(() => {
        mermaid.contentLoaded();
        mermaid.init(undefined, containerRef.current);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [code]);

  return (
    <div className="flex justify-center my-4 overflow-hidden">
      <div ref={containerRef} className="mermaid">
        {code}
      </div>
    </div>
  );
};

// Component to handle mermaid rendering for standalone content
const Mermaid = ({ chart }: { chart: string }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      const timer = setTimeout(() => {
        mermaid.contentLoaded();
        mermaid.init(undefined, containerRef.current);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [chart]);

  return (
    <div ref={containerRef} className="mermaid flex justify-center my-4 overflow-hidden">
      {chart}
    </div>
  );
};

// NEW: Timeline Component
interface TimelineEvent {
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  agent: string;
  action: string;
  message: string;
  metadata?: any;
}

const Timeline = ({ itemId }: { itemId: string }) => {
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

interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review' | 'report' | 'deliverable';
}

interface ArtifactViewerProps {
  itemId: string;
  onClose: () => void;
}

const ReviewForm = ({ reviewStatus, setReviewStatus, reviewComments, setReviewComments, submitReview }: any) => (
    <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
      <h3 className="font-bold text-gray-900">Submit Review</h3>
      <div>
        <label className="block text-sm font-medium text-gray-700">Status</label>
        <select 
          className="mt-1 block w-full border border-gray-300 rounded-md p-2"
          value={reviewStatus}
          onChange={(e: any) => setReviewStatus(e.target.value)}
        >
          <option value="APPROVED">Approved</option>
          <option value="NEEDS_REVISION">Needs Revision</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700">Comments</label>
        <textarea 
          className="mt-1 block w-full border border-gray-300 rounded-md p-2 h-32"
          value={reviewComments}
          onChange={(e: any) => setReviewComments(e.target.value)}
        />
      </div>
      <button 
        onClick={submitReview}
        className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
      >
        Submit Review
      </button>
    </div>
  );

export function ArtifactViewer({ itemId, onClose }: ArtifactViewerProps) {

  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewStatus, setReviewStatus] = useState('APPROVED');
  const [reviewComments, setReviewComments] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [itemDetails, setItemDetails] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);

  const submitReview = async () => {
    const content = `review_status: ${reviewStatus}\n\n## Comments\n${reviewComments}`;
    await saveContent('review.md', content);

    if (reviewStatus === 'APPROVED') {
      const nextStageMap: Record<string, string> = {
        'REVIEW_SPEC': 'ARCHITECTURE',
        'REVIEW_ARCH': 'TESTING',
        'REVIEW_TEST': 'APPROVED'
      };
      const nextStage = nextStageMap[itemDetails?.stage];

      if (nextStage) {
        await fetch(`${apiUrl}/api/move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: itemId, new_stage: nextStage })
        });
        alert('Review Approved! Transitioning to ' + nextStage);
        onClose(); // Close the viewer
      } else {
        alert('Review Approved!');
      }
    } else {
      alert('Feedback submitted. Task remains in ' + itemDetails?.stage);
    }
  };

  useEffect(() => {
    const fetchItemDetails = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/item/${itemId}`);
        if (res.ok) {
          const data = await res.json();
          setItemDetails(data);
        }
      } catch (e) {
        console.error('Failed to fetch item details', e);
      }
    };
    fetchItemDetails();
  }, [itemId]);

  useEffect(() => {
    const fetchArtifacts = async () => {
      try {
        if (itemDetails?.execution_policy?.mode === 'INLINE') {
          setArtifacts([{ name: 'Result', content: itemDetails.inline_output || '', type: 'review' }]);
          setLoading(false);
          return;
        }

        const getRelevantArtifacts = (stage: string) => {
          const isReviewStage = stage.startsWith('REVIEW_') || 
                                ['ARCHITECTURE', 'DESIGN', 'TESTING'].includes(stage);
          const base = isReviewStage ? ['review.md'] : [];

          if (stage === 'REVIEW_SPEC') return ['spec.md', ...base];
          if (stage === 'ARCHITECTURE') return ['spec.md', 'architecture.md', ...base];
          if (stage === 'DESIGN') return ['architecture.md', 'design.md', ...base];
          if (stage === 'TESTING') return ['architecture.md', 'tests.md', ...base];
          
          if (isReviewStage) return base;

          // If stage is DONE, we want to show the outputs
          if (stage === 'DONE') return ['execution_report.md', 'deliverables.md'];

          return ['spec.md', 'architecture.md', 'tests.md'];
        };

        const artifactNames = getRelevantArtifacts(itemDetails?.stage || 'DEFAULT');
        const fetchedArtifacts: Artifact[] = [];
        let hasError = false;

        for (const name of artifactNames) {
          try {
            const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${name}`);
            if (res.ok) {
              const content = await res.text();
              let type: any = name.replace('.md', '');
              if (name === 'execution_report.md') type = 'report';
              if (name === 'deliverables.md') type = 'deliverable';
              fetchedArtifacts.push({ name, content, type });
            }
          } catch (e: any) {
            console.error(`Failed to fetch artifact ${name}`, e);
            hasError = true;
          }
        }
        
        if (hasError && fetchedArtifacts.length === 0) {
          throw new Error('No artifacts found');
        }

        setArtifacts(fetchedArtifacts);
        setLoading(false);
      } catch (e: any) {
        console.error('Failed to fetch artifacts', e);
        setError(e.message);
        setLoading(false);
      }
    };
    fetchArtifacts();
  }, [itemDetails, itemId]);

  const saveContent = React.useCallback(async (name: string, content: string) => {
    setIsSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${name}/content`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) {
        throw new Error('Failed to save content');
      }
    } catch (e) {
      console.error('Save error:', e);
    } finally {
      setIsSaving(false);
    }
  }, [itemId]);

  const debouncedSave = React.useMemo(
    () => debounce((name: string, content: string) => saveContent(name, content), 1000),
    [saveContent]
  );

  useEffect(() => {
    return () => {
      debouncedSave.cancel();
    };
  }, [debouncedSave]);

  const handleContentChange = (newContent: string) => {
    if (!selectedArtifact) return;
    setSelectedArtifact({ ...selectedArtifact, content: newContent });
    debouncedSave(selectedArtifact.name, newContent);
  };

  useEffect(() => {
    setIsEditing(false);
  }, [selectedArtifact?.name]);

  const getInstructions = (stage: string) => {
    switch (stage) {
      case 'REVIEW_SPEC':
        return { title: 'Review Specification', steps: ['Read spec.md', 'Note technical concerns', 'Set review_status in review.md'] };
      case 'ARCHITECTURE':
        return { title: 'Architecture Review', steps: ['Read architecture.md', 'Check scalability', 'Verify integration'] };
      default:
        return null;
    }
  };

  const needsReview = itemDetails?.stage?.startsWith('REVIEW_') && !artifacts.some(a => a.name === 'review.md');
  const instructions = getInstructions(itemDetails?.stage);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading artifacts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-500">Error: {error}</div>
      </div>
    );
  }

  if (artifacts.length === 0 && !needsReview) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">No artifacts available for this item</div>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto flex flex-col justify-between shrink-0">
        <div className="p-4">
          {itemDetails && (
            <div className="mb-6 pb-4 border-b border-gray-200 text-sm text-gray-600">
              <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Item Details</h4>
              <div className="space-y-2">
                <div>
                  <span className="font-semibold">Priority:</span>{' '}
                  <span className="capitalize">{itemDetails.priority}</span>
                </div>
                <div>
                  <span className="font-semibold">Confidence:</span>{' '}
                  <span>{itemDetails.confidence_score ?? 0}%</span>
                </div>
                {itemDetails.source_type && (
                  <div>
                    <span className="font-semibold">Source:</span>{' '}
                    <div className="text-xs bg-white p-1.5 rounded mt-1 border border-gray-200 overflow-hidden text-ellipsis flex items-center gap-1">
                      <span>{itemDetails.source_type === 'url' ? '🌐' : '📁'}</span>
                      <span className="truncate text-gray-700" title={itemDetails.source_value}>
                        {itemDetails.source_value}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
          <h3 className="font-semibold text-gray-700 mb-3">Artifacts</h3>
          <div className="space-y-2">
            {artifacts.map((artifact) => (
              <button
                key={artifact.name}
                onClick={() => setSelectedArtifact(artifact)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  selectedArtifact?.name === artifact.name
                    ? 'bg-blue-100 text-blue-900'
                    : 'hover:bg-gray-100 text-gray-700'
                }`}
              >
                <div className="font-medium text-sm">{artifact.name}</div>
                <div className="text-xs text-gray-500 capitalize">{artifact.type}</div>
              </button>
            ))}
          </div>
        </div>
        
        <Timeline itemId={itemId} />
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-white">
        {selectedArtifact ? (
          <div>
            {/* Action Center - Only visible if we have instructions and no artifact selected */}
            {instructions && !selectedArtifact && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <h3 className="font-bold text-blue-900">{instructions.title}</h3>
                <ul className="list-decimal ml-5 mt-2 space-y-1 text-sm text-blue-800">
                  {instructions.steps.map((step, i) => <li key={i}>{step}</li>)}
                </ul>
              </div>
            )}
            
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">{selectedArtifact.name}</h2>
              <div className="flex items-center gap-3">
              <button
                onClick={async () => {
                  if (window.confirm(`Promote ${selectedArtifact.name} to a reusable pattern? This will train the system.`)) {
                    try {
                      const res = await fetch(`${apiUrl}/api/item/${itemId}/promote-pattern?artifact_name=${selectedArtifact.name}`, {
                        method: 'POST'
                      });
                      if (!res.ok) throw new Error('Promotion failed');
                      alert('Pattern promoted successfully!');
                    } catch (err) {
                      console.error(err);
                      alert('Error promoting pattern.');
                    }
                  }
                }}
                className="px-3 py-1 text-xs font-medium text-white bg-purple-600 rounded hover:bg-purple-700 transition-colors"
              >
                Promote to Pattern
              </button>
                {selectedArtifact.name === 'review.md' && (
                  <span className={`text-xs px-2 py-1 rounded-full transition-colors ${
                    isSaving ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {isSaving ? 'Saving...' : 'Saved'}
                  </span>
                )}
                <span className="text-sm text-gray-500 capitalize">{selectedArtifact.type}</span>
              </div>
            </div>
            {selectedArtifact.name === 'review.md' ? (
              <ReviewForm 
                reviewStatus={reviewStatus}
                setReviewStatus={setReviewStatus}
                reviewComments={reviewComments}
                setReviewComments={setReviewComments}
                submitReview={submitReview}
              />
            ) : (
              <div className="flex flex-col h-full">
                {selectedArtifact.type !== 'review' && (
                  <div className="flex justify-end mb-2">
                    <button 
                      onClick={() => setIsEditing(!isEditing)}
                      className="px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 rounded text-gray-700 transition-colors"
                    >
                      {isEditing ? 'Preview' : 'Edit'}
                    </button>
                  </div>
                )}

                {isEditing ? (
                  <textarea
                    className="w-full h-[calc(100vh-300px)] p-4 rounded-lg border border-gray-200 font-mono text-sm text-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                    value={selectedArtifact.content}
                    onChange={(e) => handleContentChange(e.target.value)}
                    placeholder={`Edit ${selectedArtifact.name}...`}
                  />
                ) : (
                  <div className="prose prose-slate max-w-none overflow-auto">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({node, inline, className, children, ...props}: any) {
                          const match = /language-mermaid/.exec(className || '')
                          return !inline && match ? (
                            <MermaidCodeBlock code={String(children).replace(/\n$/, '')} />
                          ) : (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          )
                        }
                      }}
                    >
                      {selectedArtifact.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            {needsReview ? (
              <div className="max-w-md p-8 bg-amber-50 border border-amber-200 rounded-2xl shadow-sm">
                <div className="text-4xl mb-4">📝</div>
                <h2 className="text-xl font-bold text-amber-900 mb-2">Review Required</h2>
                <p className="text-amber-800 mb-6">
                  This task is in a review stage, but no <strong>review.md</strong> has been created yet.
                  Please create a review to provide feedback or approve the current stage.
                </p>
                <div className="text-sm text-amber-700 italic">
                  Tip: Select an existing artifact (like spec.md) to start your review.
                </div>
              </div>
            ) : (
              <div className="text-gray-500">Select an artifact to view its contents</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
