import React, { useState, useEffect } from 'react';
import { debounce } from 'lodash';
import { apiUrl } from '../config';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';

// Initialize mermaid
mermaid.initialize({ startOnLoad: true, theme: 'dark' });

// Component to handle mermaid rendering within markdown
const MermaidCodeBlock = ({ code }: { code: string }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      mermaid.contentLoaded();
      // Re-run mermaid init on this container
      mermaid.init(undefined, containerRef.current);
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
  const containerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      mermaid.contentLoaded();
      mermaid.init(undefined, containerRef.current);
    }
  }, [chart]);

  return (
    <div ref={containerRef} className="mermaid flex justify-center my-4 overflow-hidden">
      {chart}
    </div>
  );
};

interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review';
}

interface ArtifactViewerProps {
  itemId: string;
  onClose: () => void;
}

// Add this before ArtifactViewer component
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
          const base = ['review.md'];
          if (stage === 'REVIEW_SPEC') return ['spec.md', ...base];
          if (stage === 'ARCHITECTURE') return ['spec.md', 'architecture.md', ...base];
          if (stage === 'DESIGN') return ['architecture.md', 'design.md', ...base];
          if (stage === 'TESTING') return ['architecture.md', 'tests.md', ...base];
          return ['spec.md', 'architecture.md', 'tests.md', ...base];
        };

        const artifactNames = getRelevantArtifacts(itemDetails?.stage || 'DEFAULT');
        const fetchedArtifacts: Artifact[] = [];
        let hasError = false;

        for (const name of artifactNames) {
          try {
            const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${name}`);
            if (res.ok) {
              const content = await res.text();
              const type = name.replace('.md', '') as any;
              fetchedArtifacts.push({ name, content, type });
            }
          } catch (e) {
            console.error(`Failed to fetch artifact ${name}`, e);
            hasError = true;
          }
        }
        
        if (hasError && fetchedArtifacts.length === 0) {
          throw new Error('No artifacts found');
        }

        setArtifacts(fetchedArtifacts);
        setLoading(false);
      } catch (e) {
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
    <div className="flex h-full">
      <div className="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto flex flex-col justify-between">
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
      </div>

      <div className="flex-1 overflow-y-auto p-6">
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
            ) : selectedArtifact.name === 'review.md' || selectedArtifact.type !== 'review' ? (
              <textarea
                className="w-full h-[calc(100vh-300px)] p-4 rounded-lg border border-gray-200 font-mono text-sm text-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                value={selectedArtifact.content}
                onChange={(e) => handleContentChange(e.target.value)}
                placeholder={`Edit ${selectedArtifact.name}...`}
              />
            ) : (
              <div className="prose prose-slate max-w-none">
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
