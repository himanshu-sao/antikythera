import React, { useState } from 'react';
let ReactMarkdown: any;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  ReactMarkdown = require('react-markdown').default;
} catch {
  // Fallback stub for testing environment
  ReactMarkdown = (props: any) => null;
}
let remarkGfm: any;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  remarkGfm = require('remark-gfm');
} catch {
  // No-op plugin for testing
  remarkGfm = () => {};
}
import { AlertCircle } from 'lucide-react';
import { Mermaid } from './artifacts/Mermaid';
import { Timeline } from './artifacts/Timeline';
import { ReviewForm } from './artifacts/ReviewForm';
import { ZoomableArtifact } from './artifacts/ZoomableArtifact';
import { useArtifacts } from '../hooks/useArtifacts';

const apiUrl = 'http://localhost:8006';

interface ArtifactViewerProps {
  itemId: string;
  onClose: () => void;
}

export function ArtifactViewer({ itemId, onClose }: ArtifactViewerProps) {
  const {
    artifacts,
    loading,
    selectedArtifact,
    setSelectedArtifact,
    error,
    reviewStatus,
    setReviewStatus,
    reviewComments,
    setReviewComments,
    isSaving,
    itemDetails,
    handleContentChange,
    submitReview,
    needsReview
  } = useArtifacts({ itemId, onClose });

  const [activeTab, setActiveTab] = useState<'technical' | 'review'>('technical');
  const [isEditing, setIsEditing] = useState(false);

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
      {/* Sidebar */}
      <div className="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto flex flex-col justify-between shrink-0">
        <div className="p-4">
          {itemDetails && (
            <>
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

              {itemDetails.blocked_reason && (
                <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded-r-lg shadow-sm animate-in fade-in slide-in-from-top-1 duration-300">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-sm font-bold text-red-800 uppercase tracking-tight">Blocking Error</h4>
                      <p className="text-sm text-red-700 mt-1 leading-relaxed">
                        {itemDetails.blocked_reason}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          <h3 className="font-semibold text-gray-700 mb-3">Artifacts</h3>
          
          <div className="flex p-1 bg-gray-200 rounded-lg mb-4">
            <button
              onClick={() => setActiveTab('technical')}
              className={`flex-1 py-1 text-xs font-medium rounded-md transition-all ${
                activeTab === 'technical' 
                  ? 'bg-white text-gray-900 shadow-sm' 
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Technical
            </button>
            <button
              onClick={() => setActiveTab('review')}
              className={`flex-1 py-1 text-xs font-medium rounded-md transition-all ${
                activeTab === 'review' 
                  ? 'bg-white text-gray-900 shadow-sm' 
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Review
            </button>
          </div>

          <div className="space-y-2">
            {activeTab === 'technical' ? (
              <>
                {artifacts
                  .filter(a => a.name !== 'review.md')
                  .map((artifact) => (
                    <button
                      key={artifact.name}
                      onClick={() => {
                        setSelectedArtifact(artifact);
                        setIsEditing(false);
                      }}
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
                {needsReview && (
                  <button
                    onClick={() => {
                      const reviewArtifact = artifacts.find(a => a.name === 'review.md');
                      if (reviewArtifact) {
                        setSelectedArtifact(reviewArtifact);
                      } else {
                        setSelectedArtifact({ name: 'review.md', content: '', type: 'review' });
                      }
                      setIsEditing(false);
                    }}
                    className="w-full text-left p-3 rounded-lg border border-dashed border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors mt-4"
                  >
                    <div className="font-bold text-sm flex items-center gap-2">
                      <span>✍️</span> Add Your Review
                    </div>
                    <div className="text-[10px] opacity-80 italic">
                      Open review.md to approve or provide feedback
                    </div>
                  </button>
                )}
              </>
            ) : (
              <>
                {artifacts
                  .filter(a => a.name === 'review.md')
                  .map((artifact) => (
                    <button
                      key={artifact.name}
                      onClick={() => {
                        setSelectedArtifact(artifact);
                        setIsEditing(false);
                      }}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        selectedArtifact?.name === artifact.name
                          ? 'bg-indigo-100 text-indigo-900'
                          : 'hover:bg-indigo-50 text-indigo-700'
                      }`}
                    >
                      <div className="font-bold text-sm flex items-center gap-2">
                        <span>✍️</span> {artifact.name}
                      </div>
                      <div className="text-xs text-indigo-500 capitalize">{artifact.type}</div>
                    </button>
                  ))}
              </>
            )}
          </div>
        </div>
        <Timeline itemId={itemId} />
      </div>

      {/* Main Content Area */}
      {selectedArtifact ? (
        <div className="flex-1 overflow-y-auto">
          <div className="p-4">
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
                          img: ({node, ...props}: any) => (
                            <ZoomableArtifact altText={props.alt}>
                              <img {...props} className="max-w-full h-auto rounded-lg shadow-sm" />
                            </ZoomableArtifact>
                          ),
                          code: ({node, className, children, ...props}: any) => {
                            const match = /language-mermaid/i.test(className || '');
                            return !className?.includes('language-mermaid') && match ? (
                              <ZoomableArtifact>
                                <Mermaid chart={String(children).replace(/\\n/g, ' ')} isCodeBlock={true} />
                              </ZoomableArtifact>
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
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center h-full">
          <div className="text-gray-500">Currently no artifact selected. Please select one from the left sidebar.</div>
        </div>
      )}
    </div>
  );
}
