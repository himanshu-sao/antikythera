import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Clock, CheckCircle2, AlertCircle, Info, FileText, CheckSquare } from 'lucide-react';
import { apiUrl } from '../config';
import { Mermaid } from './artifacts/Mermaid';
import { Timeline } from './artifacts/Timeline';
import { ReviewForm } from './artifacts/ReviewForm';
import { debounce } from 'lodash';

interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review' | 'report' | 'deliverable';
}

interface ArtifactViewerProps {
  itemId: string;
  onClose: () => void;
}

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

  useEffect(() => {
    setIsEditing(false);
  }, [selectedArtifact?.name]);

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
        onClose();
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

        // --- NEW: Auto-select review.md if in a review stage ---
        const stage = itemDetails?.stage || '';
        const isReviewStage = stage.startsWith('REVIEW_') || 
                             ['ARCHITECTURE', 'DESIGN', 'TESTING'].includes(stage);
        
        if (isReviewStage) {
          const reviewArtifact = fetchedArtifacts.find(a => a.name === 'review.md');
          if (reviewArtifact) {
            setSelectedArtifact(reviewArtifact);
          }
        }
        // ------------------------------------------------------

      } catch (e: any) {
        console.error('Failed to fetch artifacts', e);
        setError(e.message);
        setLoading(false);
      }
    };
    fetchArtifacts();
  }, [itemDetails, itemId]);

  const saveContent = async (name: string, content: string) => {
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
  };

  const debouncedSave = React.useMemo(
    () => debounce((name: string, content: string) => saveContent(name, content), 1000),
    [itemId]
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
                <div className="relative flex-1 flex flex-col min-h-[500px]">
                  {isEditing ? (
                    <textarea
                      value={selectedArtifact.content}
                      onChange={(e) => handleContentChange(e.target.value)}
                      className="flex-1 w-full p-6 font-mono text-sm bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none shadow-inner"
                    />
                  ) : (
                    <div className="group flex-1">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code: ({node, className, children, ...props}: any) => {
                            const match = /language-mermaid/i.test(className || '');
                            return !className?.includes('language-mermaid') && match ? (
                              <Mermaid chart={String(children).replace(/\n/g, ' ')} isCodeBlock={true} />
                            ) : (
                              <code className="bg-gray-100 px-1 rounded text-sm font-mono" {...props}>
                              {children}
                              </code>
                            );
                          }
                        }}
                      >
                        {selectedArtifact.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
                {selectedArtifact.type === 'report' && (
                  <div className="mt-6 border-t border-gray-200 pt-4">
                    <div className="font-bold text-gray-900 mb-2">Execution Report Details</div>
                    <div className="text-sm text-gray-600">
                      {selectedArtifact.content.split('\n').filter(l => l.trim() !== '').slice(1).join('\n')}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-gray-500">Curently no artifact selected. Please select one from the left sidebar.</div>
          </div>
        )}
      </div>
    </div>
  );
}
