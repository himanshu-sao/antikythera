import React, { useState, useEffect } from 'react';
import { Settings, Brain, Zap, MessageSquare, Check, X, ChevronRight, AlertCircle, Info, FileText, Send } from 'lucide-react';
import { apiUrl } from '../config';

interface CognitiveDelta {
  delta_id: string;
  target_artifact: 'user.md' | 'skills.md' | 'memory.md';
  change_type: 'ADD' | 'REMOVE' | 'REPLACE' | 'REVISE';
  original_content?: string;
  proposed_content: string;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'REFINED';
  confidence_score: number;
  created_at: string;
  refined_by_comment?: string;
}

interface BrainArtifact {
  name: string;
  content: string;
}

export function BrainSettings() {
  const [activeTab, setActiveTab] = useState<'artifacts' | 'action-center'>('artifacts');
  const [artifacts, setArtifacts] = useState<Record<string, BrainArtifact>>({});
  const [deltas, setDeltas] = useState<CognitiveDelta[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isCommenting, setIsCommenting] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [activeDeltaComment, setActiveDeltaComment] = useState<string | null>(null);
  const [comment, setComment] = useState('');

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const artRes = await fetch(`${apiUrl}/api/brain/artifacts`);
      if (artRes.ok) {
        const artData = await artRes.json();
        setArtifacts(artData);
      }

      const deltaRes = await fetch(`${apiUrl}/api/brain/deltas/pending`);
      if (deltaRes.ok) {
        const deltaData = await deltaRes.json();
        setDeltas(deltaData);
      }
    } catch (e) {
      console.error('Failed to fetch brain data', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const handleArtifactSelect = (name: string) => {
    setSelectedArtifact(name);
    setEditContent(artifacts[name]?.content || '');
    setIsEditing(false);
    setIsCommenting(false);
    setCommentText('');
  };

  const saveInlineEdit = async () => {
    if (!selectedArtifact) return;
    setIsSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/brain/artifacts/${selectedArtifact}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent }),
      });
      if (res.ok) {
        setArtifacts(prev => ({
          ...prev,
          [selectedArtifact]: { name: selectedArtifact, content: editContent }
        }));
        setIsEditing(false);
      } else {
        alert('Failed to save changes.');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const submitArtifactComment = async () => {
    if (!selectedArtifact || !commentText.trim()) return;
    try {
      const res = await fetch(`${apiUrl}/api/observer/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: 'ARTIFACT_COMMENT',
          event_data: {
            target_artifact: selectedArtifact,
            comment: commentText
          }
        }),
      });
      if (res.ok) {
        setIsCommenting(false);
        setCommentText('');
        fetchAllData();
      } else {
        alert('Failed to send comment.');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveDelta = async (deltaId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/brain/deltas/${deltaId}/approve`, { method: 'POST' });
      if (res.ok) {
        setDeltas(prev => prev.filter(d => d.delta_id !== deltaId));
        fetchAllData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectDelta = async (deltaId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/brain/deltas/${deltaId}/reject`, { method: 'POST' });
      if (res.ok) {
        setDeltas(prev => prev.filter(d => d.delta_id !== deltaId));
        fetchAllData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRefineDelta = async (deltaId: string) => {
    const targetComment = activeDeltaComment || comment;
    if (!targetComment.trim()) return;
    try {
      const res = await fetch(`${apiUrl}/api/brain/deltas/${deltaId}/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: targetComment }),
      });
      if (res.ok) {
        setComment('');
        setActiveDeltaComment(null);
        fetchAllData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-full text-gray-500">Loading Cognitive Brain...</div>;
  }

  return (
    <div className="flex h-full bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-600" />
            Cognitive Brain
          </h2>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <button
            onClick={() => setActiveTab('artifacts')}
            className={`w-full flex items-center justify-between p-3 rounded-lg transition-colors ${
              activeTab === 'artifacts' ? 'bg-purple-50 text-purple-700' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <span className="flex items-center gap-3">
              <Settings className="w-4 h-4" />
              Knowledge Base
            </span>
            <ChevronRight className={`w-4 h-4 transition-transform ${activeTab === 'artifacts' ? 'rotate-90' : ''}`} />
          </button>
          <button
            onClick={() => setActiveTab('action-center')}
            className={`w-full flex items-center justify-between p-3 rounded-lg transition-colors ${
              activeTab === 'action-center' ? 'bg-orange-50 text-orange-700' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <span className="flex items-center gap-3">
              <Zap className="w-4 h-4" />
              Action Center
            </span>
            {deltas.length > 0 && (
              <span className="bg-orange-500 text-white text-[10px] px-2 py-0.5 rounded-full">
                {deltas.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'artifacts' ? (
          <div className="p-8 flex gap-8 h-full">
            {/* Artifact List */}
            <div className="w-1/3 space-y-4">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Core Artifacts</h3>
              {Object.values(artifacts).map(art => (
                <div
                  key={art.name}
                  onClick={() => handleArtifactSelect(art.name)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    selectedArtifact === art.name
                      ? 'bg-white border-purple-500 shadow-md ring-2 ring-purple-100'
                      : 'bg-white border-gray-200 hover:border-purple-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div className="font-medium text-gray-900">{art.name}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Editor */}
            <div className="flex-1 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col">
              {selectedArtifact ? (
                <>
                  <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                    <h3 className="font-bold text-gray-800">{selectedArtifact}</h3>
                    <div className="flex gap-2">
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => setIsEditing(false)}
                            className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={saveInlineEdit}
                            disabled={isSaving}
                            className="px-4 py-1.5 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg disabled:opacity-50"
                          >
                            {isSaving ? 'Saving...' : 'Save Changes'}
                          </button>
                        </>
                      ) : isCommenting ? (
                        <div className="flex gap-2">
                          <input
                            autoFocus
                            type="text"
                            value={commentText}
                            onChange={(e) => setCommentText(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && submitArtifactComment()}
                            placeholder="Enter feedback for AI..."
                            className="text-sm border border-orange-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-orange-500 outline-none"
                          />
                          <button
                            onClick={submitArtifactComment}
                            className="p-1.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
                          >
                            <Send className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setIsCommenting(false)}
                            className="p-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              setIsEditing(true);
                              setEditContent(artifacts[selectedArtifact]?.content || '');
                            }}
                            className="px-4 py-1.5 text-sm font-medium text-purple-600 hover:bg-purple-50 rounded-lg"
                          >
                            Edit Inline
                          </button>
                          <button
                            onClick={() => {
                              setIsCommenting(true);
                              setCommentText('');
                            }}
                            className="px-4 py-1.5 text-sm font-medium text-orange-600 hover:bg-orange-50 rounded-lg flex items-center gap-2"
                          >
                            <MessageSquare className="w-4 h-4" />
                            Comment for AI
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex-1 overflow-auto p-6">
                    {isEditing ? (
                      <textarea
                        className="w-full h-full font-mono text-sm p-4 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                      />
                    ) : (
                      <pre className="whitespace-pre-wrap font-mono text-sm text-gray-700">{artifacts[selectedArtifact]?.content}</pre>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-gray-400 italic">
                  Select an artifact to view or edit.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-8 max-w-4xl mx-auto">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900">Action Center</h2>
              <p className="text-gray-500">Review proposed intelligence updates from the Cognitive Observer.</p>
            </div>

            {deltas.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-gray-200 rounded-3xl p-12 text-center">
                <div className="mx-auto w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
                  <Check className="w-8 h-8 text-gray-300" />
                </div>
                <h3 className="text-lg font-medium text-gray-900">No pending updates</h3>
                <p className="text-gray-500">The brain is currently synchronized with your current state.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {deltas.map(delta => (
                  <div key={delta.delta_id} className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="p-6 border-b border-gray-100 bg-gray-50/50">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-[10px] font-bold rounded uppercase tracking-wider">
                              {delta.change_type}
                            </span>
                            <span className="text-sm font-medium text-gray-900">{delta.target_artifact}</span>
                          </div>
                          <p className="text-sm text-gray-600 italic">"{delta.reason}"</p>
                        </div>
                        <div className="flex items-center gap-1 text-xs font-medium text-orange-600 bg-orange-50 px-2 py-1 rounded-full">
                          <Zap className="w-3 h-3" />
                          {delta.confidence_score}% Confidence
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-xs text-gray-500">
                        <div>
                          <span className="font-semibold uppercase text-[10px]">Original Content</span>
                          <div className="mt-1 p-2 bg-red-50/50 border border-red-100 rounded max-h-32 overflow-y-auto font-mono">
                            {delta.original_content || '(empty)'}
                          </div>
                        </div>
                        <div>
                          <span className="font-semibold uppercase text-[10px]">Proposed Content</span>
                          <div className="mt-1 p-2 bg-green-50/50 border border-green-100 rounded max-h-32 overflow-y-auto font-mono text-green-900">
                            {delta.proposed_content}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="p-6 space-y-4">
                      {delta.status === 'REFINED' && (
                        <div className="bg-blue-50 border border-blue-100 p-3 rounded-lg text-sm text-blue-800 flex gap-3">
                          <MessageSquare className="w-5 h-5 flex-shrink-0" />
                          <div>
                            <span className="font-bold">User feedback applied:</span>
                            <p className="italic">"{delta.refined_by_comment}"</p>
                          </div>
                        </div>
                      )}

                      <div className="flex gap-3">
                        <button
                          onClick={() => handleApproveDelta(delta.delta_id)}
                          className="flex-1 flex items-center justify-center gap-2 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium text-sm"
                        >
                          <Check className="w-4 h-4" />
                          Approve & Commit
                        </button>
                        <button
                          onClick={() => handleRejectDelta(delta.delta_id)}
                          className="flex-1 flex items-center justify-center gap-2 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors font-medium text-sm"
                        >
                          <X className="w-4 h-4" />
                          Reject
                        </button>
                      </div>

                      <div className="pt-4 border-t border-gray-100">
                        <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Refine via Comment</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={activeDeltaComment !== null ? activeDeltaComment : comment}
                            onChange={(e) => activeDeltaComment !== null ? setActiveDeltaComment(e.target.value) : setComment(e.target.value)}
                            placeholder="e.g., 'Make this more concise' or 'Add the Python example'"
                            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-orange-500 outline-none"
                            onKeyDown={(e) => e.key === 'Enter' && handleRefineDelta(delta.delta_id)}
                          />
                          <button
                            onClick={() => {
                              if (activeDeltaComment !== null) {
                                handleRefineDelta(delta.delta_id);
                              } else {
                                setActiveDeltaComment(comment);
                              }
                            }}
                            disabled={!comment.trim() && activeDeltaComment === null}
                            className="px-4 py-1.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 text-sm font-medium"
                          >
                            {activeDeltaComment !== null ? 'Send' : 'Refine'}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
