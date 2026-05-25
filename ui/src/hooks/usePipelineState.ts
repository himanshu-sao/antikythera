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
      if (!res.ok) throw new Error('Failed to update item');
      await fetchState();
    } catch (e: any) { 
      toast.error(e.message); 
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete item');
      await fetchState();
      toast.success("Item deleted");
    } catch (e: any) { 
      toast.error(e.message); 
    }
  };

  const handleCreateItem = async (itemData: any) => {
    const itemId = itemData.id.toUpperCase();
    try {
      const res = await fetch(`${apiUrl}/api/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: itemId,
          ...itemData
        }),
      });
      if (!res.ok) throw new Error('Failed to create item');
      await fetchState();
      toast.success("New idea created");
      return true;
    } catch (e: any) {
      toast.error(e.message);
      return false;
    }
  };

  const handleMoveItem = async (itemId: string, targetStage: string, targetOrder: number) => {
    try {
      const res = await fetch(`${apiUrl}/api/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, new_stage: targetStage, order: targetOrder }),
      });
      if (res.ok) {
        await fetchState();
      }
    } catch (e) { 
      console.error("Failed to move item", e); 
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
    handleMoveItem
  };
}
