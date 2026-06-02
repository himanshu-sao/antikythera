import { useState, useCallback } from 'react';
import { apiUrl } from '../config';

// Custom hook for managing selected item state
export function useSelectedItem() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);

  // Function to handle card click
  const handleCardClick = useCallback(async (id: string) => {
    setSelectedId(id);
    setEditMode(false);
    try {
      const res = await fetch(`${apiUrl}/api/workflows/items/${id}/run`);
      if (res.ok) {
        const data = await res.json();
        if (data.run_id) setSelectedRunId(data.run_id);
      }
    } catch (e) { 
      console.error("Failed to check workflow binding", e); 
    }
  }, []);

  // Function to close the selected item
  const closeSelectedItem = useCallback(() => {
    setSelectedId(null);
    setEditMode(false);
    setSelectedRunId(null);
  }, []);

  // Function to toggle edit mode
  const toggleEditMode = useCallback(() => {
    setEditMode(prev => !prev);
  }, []);

  return {
    selectedId,
    selectedRunId,
    editMode,
    handleCardClick,
    closeSelectedItem,
    toggleEditMode,
    setSelectedId,
    setSelectedRunId,
    setEditMode,
  };
}