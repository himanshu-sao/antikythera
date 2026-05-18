import React, { useState, useEffect } from 'react';
import { debounce } from 'lodash';

interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review';
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
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const fetchArtifacts = async () => {
      try {
        const artifactNames = ['spec.md', 'architecture.md', 'tests.md', 'review.md'];
        const fetchedArtifacts: Artifact[] = [];

        for (const name of artifactNames) {
          try {
            const res = await fetch(`http://localhost:8000/api/item/${itemId}/artifact/${name}`);
            if (res.ok) {
              const content = await res.text();
              const type = name.replace('.md', '') as any;
              fetchedArtifacts.push({ name, content, type });
            }
          } catch (e) {
            console.error(`Failed to fetch ${name}`, e);
          }
        }
        setArtifacts(fetchedArtifacts);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchArtifacts();
  }, [itemId]);

  const saveContent = async (content: string) => {
    if (!selectedArtifact) return;
    setIsSaving(true);
    try {
      const res = await fetch(`http://localhost:8000/api/item/${itemId}/artifact/${selectedArtifact.name}/content`, {
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

  const debouncedSave = debounce(saveContent, 1000);

  const handleContentChange = (newContent: string) => {
    if (!selectedArtifact) return;
    setSelectedArtifact({ ...selectedArtifact, content: newContent });
    debouncedSave(newContent);
  };

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

  if (artifacts.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">No artifacts available for this item</div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto">
        <div className="p-4">
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
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">{selectedArtifact.name}</h2>
              <div className="flex items-center gap-3">
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
              <textarea
                className="w-full h-[calc(100vh-300px)] p-4 rounded-lg border border-gray-200 font-mono text-sm text-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                value={selectedArtifact.content}
                onChange={(e) => handleContentChange(e.target.value)}
                placeholder="Write your review here..."
              />
            ) : (
              <pre className="bg-gray-50 p-4 rounded-lg overflow-x-auto text-sm text-gray-800 whitespace-pre-wrap">
                {selectedArtifact.content}
              </pre>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-gray-500">Select an artifact to view its contents</div>
          </div>
        )}
      </div>
    </div>
  );
}
