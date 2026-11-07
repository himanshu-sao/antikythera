import { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';
import type { PipelineState } from '../types/legacy-pipeline';
import { apiFetch } from '../api/client';

export function usePipelineState() {
  const [state, setState] = useState<PipelineState>({ items: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Set false on unmount so in-flight fetches and the poll loop stop touching state.
  const mountedRef = useRef(true);

  const fetchState = useCallback(async () => {
    try {
      setError(null);
      const res = await apiFetch(`${apiUrl}/api/state`);
      if (!res.ok) throw new Error('Failed to fetch state');
      const data = await res.json();
      if (mountedRef.current) setState(data);
    } catch (e: any) {
      if (!mountedRef.current) return;
      console.error("Failed to fetch state", e);
      setError(e.message || 'Failed to load data');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const POLL_INTERVAL_MS = 10000;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = () => {
      if (!mountedRef.current) return;
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    const poll = async () => {
      timer = null;
      await fetchState();
      schedule();
    };

    poll();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchState();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      mountedRef.current = false;
      if (timer !== null) clearTimeout(timer);
      timer = null;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchState]);

  const handleUpdateItem = async (itemId: string, updates: any) => {
    try {
      const res = await apiFetch(`${apiUrl}/api/item/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        let errorMessage = 'Failed to update item';
        try {
          const errorData = await res.json();
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch (e) {}
        throw new Error(errorMessage);
      }
      await fetchState();
    } catch (e: any) { 
      toast.error(e.message); 
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      const res = await apiFetch(`${apiUrl}/api/item/${itemId}`, { method: 'DELETE' });
      if (!res.ok) {
        let errorMessage = 'Failed to delete item';
        try {
          const errorData = await res.json();
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch (e) {}
        throw new Error(errorMessage);
      }
      await fetchState();
      toast.success("Item deleted");
    } catch (e: any) { 
      toast.error(e.message); 
    }
  };

  const handleCreateItem = async (itemData: any) => {
    try {
      const res = await apiFetch(`${apiUrl}/api/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemData.id.toUpperCase(),
          title: itemData.title,
          goal: itemData.goal,
          description: itemData.description,
          priority: itemData.priority,
          complexity: itemData.complexity,
          source_type: itemData.source_type,
          source_value: itemData.source_value,
          due_date: itemData.due_date
        }),
      });

      if (!res.ok) {
        let errorMessage = 'Failed to create item';
        try {
          const errorData = await res.json();
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch (e) {}
        throw new Error(errorMessage);
      }

      await fetchState();
      toast.success("New idea created");
      return true;
    } catch (e: any) {
      toast.error(e.message);
      return false;
    }
  };

  const handleReorder = async (stage: string, ordered_ids: string[]) => {
  try {
    const res = await apiFetch(`${apiUrl}/api/items/reorder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage, ordered_ids }), // matches ReorderRequest schema
    });
    if (!res.ok) {
      let errorMessage = 'Failed to reorder items';
      try {
        const errorData = await res.json();
        if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
        } else if (errorData.detail) {
          errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch (e) {}
      throw new Error(errorMessage);
    }
    if (res.ok) {
      await fetchState();
    }
  } catch (e: any) {
    toast.error(e.message);
  }
};

const handleMoveItem = async (itemId: string, targetStage: string, targetOrder: number) => {
    try {
      const res = await apiFetch(`${apiUrl}/api/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, new_stage: targetStage, order: targetOrder }),
      });
      if (!res.ok) {
        let errorMessage = 'Failed to move item';
        try {
          const errorData = await res.json();
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((d: any) => d.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch (e) {}
        throw new Error(errorMessage);
      }
      if (res.ok) {
        await fetchState();
      }
    } catch (e: any) { 
      toast.error(e.message);
    }
  };

  return {
    state,
    setState,
    loading,
    error,
    fetchState,
    handleUpdateItem,
    handleDeleteItem,
    handleCreateItem,
    handleMoveItem,
    handleReorder
  };
}
