import { useState, useCallback } from 'react';
import { DragEndEvent, DragStartEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

// Custom hook for managing drag and drop functionality
export function useDragAndDrop() {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(String(event.active.id));
  }, []);

  const handleDragEnd = useCallback(async (
    event: DragEndEvent,
    state: any,
    handleMoveItem: (itemId: string, targetStage: string, targetOrder: number) => Promise<void>,
    STAGES: string[]
  ) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const itemId = String(active.id);
    const overId = String(over.id);
    if (!itemId || !overId) return;

    const activeItem = state.items[itemId];
    if (!activeItem) return;

    let targetStage = '';
    let targetOrder = 0;

    const isStage = STAGES.includes(overId);
    if (isStage) {
      targetStage = overId;
      const columnItems = Object.entries(state.items)
        .map(([id, item]: [string, any]) => ({ ...item, id }))
        .filter((item: any) => item.stage === targetStage && item.id !== itemId)
        .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0));
      targetOrder = columnItems.length;
    } else {
      const overItem = state.items[overId];
      if (!overItem) return;
      targetStage = overItem.stage;
      const columnItems = Object.entries(state.items)
        .map(([id, item]: [string, any]) => ({ ...item, id }))
        .filter((item: any) => item.stage === targetStage && item.id !== itemId)
        .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0));
      const overIndex = columnItems.findIndex((item: any) => item.id === overId);
      targetOrder = overIndex === -1 ? columnItems.length : overIndex;
    }

    if (activeItem.stage === targetStage && (activeItem.order ?? 0) === targetOrder) return;
    await handleMoveItem(itemId, targetStage, targetOrder);
  }, []);

  return {
    activeId,
    sensors,
    handleDragStart,
    handleDragEnd,
  };
}