// Pure decision logic for a Kanban drag-end event, kept out of App.tsx so it can be tested.

export interface DraggableItem {
  stage: string;
  order?: number | null;
}

export type DragAction =
  | { type: 'none' }
  | { type: 'reorder'; stage: string; orderedIds: string[] }
  | { type: 'move'; itemId: string; stage: string; order: number };

export interface DragInput {
  items: Record<string, DraggableItem>;
  stages: readonly string[];
  /** Id of the dragged card. */
  activeId: string;
  /** Id of what it was dropped on: a column (stage name) or another card. */
  overId: string;
}

const NONE: DragAction = { type: 'none' };

function idsInStage(items: Record<string, DraggableItem>, stage: string): string[] {
  // Array.prototype.sort is stable, so items without an order keep insertion order.
  return Object.keys(items)
    .filter(id => items[id].stage === stage)
    .sort((a, b) => (items[a].order ?? 0) - (items[b].order ?? 0));
}

/**
 * Decide what a drop should do.
 *
 * - same stage            -> 'reorder' with the full new ordering (or 'none' if nothing changes)
 * - different stage       -> 'move' to the target index (always, including into an empty column
 *                            and for items that have no `order`)
 * - dropped on itself, an unknown target or an unknown dragged item -> 'none'
 */
export function computeDragAction({ items, stages, activeId, overId }: DragInput): DragAction {
  if (!activeId || !overId) return NONE;
  const activeItem = items[activeId];
  if (!activeItem) return NONE;
  if (overId === activeId) return NONE;

  let targetStage: string;
  let targetOrder: number;

  if (stages.includes(overId)) {
    // Dropped on a column: append to its end.
    targetStage = overId;
    targetOrder = idsInStage(items, targetStage).filter(id => id !== activeId).length;
  } else {
    const overItem = items[overId];
    if (!overItem) return NONE;
    targetStage = overItem.stage;
    const others = idsInStage(items, targetStage).filter(id => id !== activeId);
    const overIndex = others.indexOf(overId);
    targetOrder = overIndex === -1 ? others.length : overIndex;
  }

  if (activeItem.stage !== targetStage) {
    return { type: 'move', itemId: activeId, stage: targetStage, order: targetOrder };
  }

  const orderedIds = idsInStage(items, targetStage);
  const fromIndex = orderedIds.indexOf(activeId);
  if (fromIndex !== -1) orderedIds.splice(fromIndex, 1);
  orderedIds.splice(Math.min(targetOrder, orderedIds.length), 0, activeId);
  // Identical ordering: no network call.
  if (fromIndex === orderedIds.indexOf(activeId)) return NONE;
  return { type: 'reorder', stage: targetStage, orderedIds };
}
