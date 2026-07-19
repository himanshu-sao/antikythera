import { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';
import type { PipelineItem, PipelineState } from '../types';

export function usePipelineState() {
  const [state, setState] = useState<PipelineState>({ items: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchState = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch(`${apiUrl}/api/state`);
      if (!res.ok) throw new Error('Failed to fetch state');
      const data = await res.json();
      setState(data);
    } catch (e: any) {
      console.error("Failed to fetch state", e);
      setError(e.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let currentDelay = 10000;
    const poll = async () => {
      await fetchState();
      setTimeout(poll, currentDelay);
    };

    poll();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchState();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [fetchState]);

  const handleUpdateItem = async (itemId: string, updates: any) => {
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}`, {
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
      const res = await fetch(`${apiUrl}/api/item/${itemId}`, { method: 'DELETE' });
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
      const res = await fetch(`${apiUrl}/api/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemData.id.toUpperCase(),
          title: itemData.title,
          goal: itemData.goal,
          description: itemData.description,
          priority: itemData.priority,
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
    const res = await fetch(`${apiUrl}/api/items/reorder`, {
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
      const res = await fetch(`${apiUrl}/api/move`, {
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
