import { useState, useEffect, useCallback, useMemo } from 'react';
import { debounce } from 'lodash';
import { apiUrl } from '../config';

export interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review' | 'report' | 'deliverable';
}

interface UseArtifactsProps {
  itemId: string;
  onClose: () => void;
}

export function useArtifacts({ itemId, onClose }: UseArtifactsProps) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewStatus, setReviewStatus] = useState('APPROVED');
  const [reviewComments, setReviewComments] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [itemDetails, setItemDetails] = useState<any>(null);

  // Reset selection when item changes
  useEffect(() => {
    setSelectedArtifact(null);
    setReviewStatus('APPROVED');
    setReviewComments('');
  }, [itemId]);

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

  const getRelevantArtifacts = useCallback((stage: string) => {
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
  }, []);

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

  const debouncedSave = useMemo(
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

  const fetchArtifacts = useCallback(async () => {
    try {
      if (itemDetails?.execution_policy?.mode === 'INLINE') {
        const inlineArtifact: Artifact[] = [{ name: 'Result', content: itemDetails.inline_output || '', type: 'review' }];
        setArtifacts(inlineArtifact);
        setLoading(false);
        return inlineArtifact;
      }

      const artifactNames = getRelevantArtifacts(itemDetails?.stage || 'DEFAULT');
      const fetchedArtifacts: Artifact[] = [];
      let hasError = false;

      for (const name of artifactNames) {
        try {
          const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${name}`);
          if (res.ok) {
            const content = await res.text();
            let type: Artifact['type'] = name.replace('.md', '') as Artifact['type'];
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

      const stage = itemDetails?.stage || '';
      const isReviewStage = stage.startsWith('REVIEW_') || 
                           ['ARCHITECTURE', 'DESIGN', 'TESTING'].includes(stage);
      
      if (isReviewStage) {
        const reviewArtifact = fetchedArtifacts.find(a => a.name === 'review.md');
        if (reviewArtifact) {
          setSelectedArtifact(reviewArtifact);
        }
      }

      return fetchedArtifacts;
    } catch (e: any) {
      console.error('Failed to fetch artifacts', e);
      setError(e.message);
      setLoading(false);
      return [];
    }
  }, [itemDetails, itemId, getRelevantArtifacts]);

  useEffect(() => {
    fetchArtifacts();
  }, [fetchArtifacts]);

  const needsReview = itemDetails?.stage?.startsWith('REVIEW_') && !artifacts.some(a => a.name === 'review.md');

  return {
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
    needsReview,
  };
}
