import React, { useState, useEffect } from 'react';
import { useArtifacts } from '../../hooks/useArtifacts';

interface ArtifactViewerProps {
  itemId: string;
  onClose: () => void;
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ 
  itemId, 
  onClose 
}) => {
  const { artifacts, loading, error } = useArtifacts(itemId);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-300"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded-lg">
        <h3 className="font-bold">Error loading artifacts</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!artifacts || artifacts.length === 0) {
    return (
      <div className="p-4 text-gray-600 bg-gray-50 rounded-lg text-center">
        <p>No artifacts found for this item.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="border-b pb-2">
        <h2 className="text-xl font-bold">Artifacts</h2>
        <p className="text-sm text-gray-600">Generated artifacts for {itemId}</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {artifacts.map((artifact) => (
          <div 
            key={artifact.name} 
            className="border rounded-lg overflow-hidden"
          >
            <div className="bg-gray-100 px-4 py-2 border-b">
              <h3 className="font-medium">{artifact.name}</h3>
              <p className="text-xs text-gray-600">{artifact.path}</p>
            </div>
            <div className="p-4 bg-white">
              <pre className="text-xs whitespace-pre-wrap">
                {artifact.content}
              </pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};