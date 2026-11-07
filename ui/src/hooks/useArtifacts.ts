import { useState, useEffect, useCallback, useMemo } from 'react';
import { debounce } from 'lodash';
import { apiUrl } from '../config';
import { apiFetch } from '../api/client';

export interface Artifact {
  name: string;
  content: string;
  type: 'spec' | 'architecture' | 'tests' | 'review' | 'report' | 'deliverable';
}

/** Stage an item moves to after an APPROVED review (the forward step of the review gate). */
const NEXT_STAGE_ON_APPROVE: Record<string, string> = {
  'REVIEW_SPEC': 'ARCHITECTURE',
  'REVIEW_ARCH': 'TESTING',
  'REVIEW_TEST': 'APPROVED',
};

/** A move the backend refused (422). Held so the user can explicitly force it. */
export interface GatedMove {
  stage: string;
  reason: string;
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail) return JSON.stringify(detail);
  } catch {
    // Non-JSON body: fall through to the generic reason.
  }
  return 'the move rules do not allow it yet';
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
  const [gatedMove, setGatedMove] = useState<GatedMove | null>(null);

  // Reset selection when item changes
  useEffect(() => {
    setSelectedArtifact(null);
    setReviewStatus('APPROVED');
    setReviewComments('');
    setGatedMove(null);
  }, [itemId]);

  useEffect(() => {
    const fetchItemDetails = async () => {
      try {
        const res = await apiFetch(`${apiUrl}/api/item/${itemId}`);
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
      const res = await apiFetch(`${apiUrl}/api/item/${itemId}/artifact/${name}/content`, {
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

  /**
   * Record the review through POST /api/item/{id}/review (D5). The backend sets review_status,
   * appends the comment to review.md and the item history. An APPROVED review then requests the
   * normal forward move; a NEEDS_REVISION review never moves the item.
   */
  const submitReview = async () => {
    const reviewRes = await apiFetch(`${apiUrl}/api/item/${itemId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: reviewStatus, comment: reviewComments }),
    });
    if (!reviewRes.ok) {
      alert(`Could not record the review (HTTP ${reviewRes.status}). Nothing was moved.`);
      return;
    }

    if (reviewStatus !== 'APPROVED') {
      alert('Feedback submitted. Task remains in ' + itemDetails?.stage);
      return;
    }

    const nextStage = NEXT_STAGE_ON_APPROVE[itemDetails?.stage];
    if (!nextStage) {
      alert('Review Approved!');
      return;
    }
    await requestMove(nextStage, false);
  };

  /** Move the item. `force` is only ever true from the explicit "Force move" action. */
  const requestMove = async (newStage: string, force: boolean) => {
    const body: Record<string, unknown> = { item_id: itemId, new_stage: newStage };
    if (force) body.force = true;
    const res = await apiFetch(`${apiUrl}/api/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      setGatedMove(null);
      alert((force ? 'Forced move to ' : 'Review Approved! Transitioning to ') + newStage);
      onClose();
      return;
    }
    if (res.status === 422 && !force) {
      const reason = await readErrorDetail(res);
      setGatedMove({ stage: newStage, reason });
      alert(`Review recorded, but the move to ${newStage} was blocked: ${reason}. Use "Force move" to override.`);
      return;
    }
    alert(`Move to ${newStage} failed (HTTP ${res.status}). The item was not moved.`);
  };

  /** Explicit override for a gated move. Only reachable through the labelled "Force move" control. */
  const forceMove = async () => {
    if (!gatedMove) return;
    await requestMove(gatedMove.stage, true);
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
          const res = await apiFetch(`${apiUrl}/api/item/${itemId}/artifact/${name}`);
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
    gatedMove,
    forceMove,
    needsReview,
  };
}
