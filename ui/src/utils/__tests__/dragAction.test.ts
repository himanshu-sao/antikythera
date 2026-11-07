import { describe, test, expect } from 'vitest';
import { computeDragAction, type DraggableItem } from '../dragAction';

const STAGES = ['INTAKE', 'REFINEMENT', 'DONE'] as const;

function items(spec: Record<string, [string, number | undefined]>): Record<string, DraggableItem> {
  const out: Record<string, DraggableItem> = {};
  for (const [id, [stage, order]] of Object.entries(spec)) {
    out[id] = order === undefined ? { stage } : { stage, order };
  }
  return out;
}

const run = (it: Record<string, DraggableItem>, activeId: string, overId: string) =>
  computeDragAction({ items: it, stages: STAGES, activeId, overId });

describe('computeDragAction: same stage', () => {
  const board = items({ A: ['INTAKE', 0], B: ['INTAKE', 1], C: ['INTAKE', 2] });

  test('dragging A onto C reorders to B, C, A... A lands at the index C had among the others', () => {
    // others (without A) = [B, C]; C is at index 1 -> A inserted at 1 -> B, A, C
    expect(run(board, 'A', 'C')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['B', 'A', 'C'] });
  });

  test('dragging C onto A moves C to the front', () => {
    expect(run(board, 'C', 'A')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['C', 'A', 'B'] });
  });

  test('dropping on the column itself appends to the end', () => {
    expect(run(board, 'A', 'INTAKE')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['B', 'C', 'A'] });
  });

  test('dropping the last card on its own column is a no-op', () => {
    expect(run(board, 'C', 'INTAKE')).toEqual({ type: 'none' });
  });

  test('dropping onto the card already just before it leaves the order unchanged', () => {
    // B dropped on C: others=[A,C], C idx 1 -> B at 1 -> A,B,C == original
    expect(run(board, 'B', 'C')).toEqual({ type: 'none' });
  });

  test('uses order values, not insertion order, to sort', () => {
    const it = items({ A: ['INTAKE', 5], B: ['INTAKE', 1], C: ['INTAKE', 3] });
    // sorted: B(1), C(3), A(5). Drag A onto B -> A first.
    expect(run(it, 'A', 'B')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['A', 'B', 'C'] });
  });

  test('ignores cards from other stages', () => {
    const it = items({ A: ['INTAKE', 0], B: ['INTAKE', 1], X: ['DONE', 0] });
    expect(run(it, 'A', 'B')).toEqual({ type: 'none' });
    expect(run(it, 'B', 'A')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['B', 'A'] });
  });

  test('items without an order keep insertion order and can be reordered', () => {
    const it = items({ A: ['INTAKE', undefined], B: ['INTAKE', undefined], C: ['INTAKE', undefined] });
    expect(run(it, 'C', 'A')).toEqual({ type: 'reorder', stage: 'INTAKE', orderedIds: ['C', 'A', 'B'] });
  });
});

describe('computeDragAction: cross stage', () => {
  test('moves to the index of the card it was dropped on', () => {
    const it = items({ A: ['INTAKE', 0], X: ['REFINEMENT', 0], Y: ['REFINEMENT', 1] });
    expect(run(it, 'A', 'Y')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 1 });
    expect(run(it, 'A', 'X')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 0 });
  });

  test('dropping on a populated column appends at the end', () => {
    const it = items({ A: ['INTAKE', 0], X: ['REFINEMENT', 0], Y: ['REFINEMENT', 1] });
    expect(run(it, 'A', 'REFINEMENT')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 2 });
  });

  test('U1: an item with no order dropped into an empty column is moved (not silently ignored)', () => {
    const it = items({ A: ['INTAKE', undefined] });
    expect(run(it, 'A', 'DONE')).toEqual({ type: 'move', itemId: 'A', stage: 'DONE', order: 0 });
  });

  test('U1: an item with order 0 dropped into an empty column is moved', () => {
    const it = items({ A: ['INTAKE', 0] });
    expect(run(it, 'A', 'REFINEMENT')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 0 });
  });

  test('a card with a stale order equal to the target index is still moved', () => {
    const it = items({ A: ['INTAKE', 2], X: ['REFINEMENT', 0], Y: ['REFINEMENT', 1] });
    expect(run(it, 'A', 'REFINEMENT')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 2 });
  });

  test('moving into a column whose cards have no order uses insertion index', () => {
    const it = items({ A: ['INTAKE', 0], X: ['REFINEMENT', undefined], Y: ['REFINEMENT', undefined] });
    expect(run(it, 'A', 'Y')).toEqual({ type: 'move', itemId: 'A', stage: 'REFINEMENT', order: 1 });
  });
});

describe('computeDragAction: guards', () => {
  const board = items({ A: ['INTAKE', 0], B: ['INTAKE', 1] });

  test('dropping a card onto itself is a no-op (it must not jump to the end)', () => {
    expect(run(board, 'A', 'A')).toEqual({ type: 'none' });
  });

  test('unknown over id is a no-op', () => {
    expect(run(board, 'A', 'NOPE')).toEqual({ type: 'none' });
  });

  test('unknown dragged id is a no-op', () => {
    expect(run(board, 'NOPE', 'B')).toEqual({ type: 'none' });
    expect(run(board, 'NOPE', 'DONE')).toEqual({ type: 'none' });
  });

  test('empty ids are a no-op', () => {
    expect(run(board, '', 'B')).toEqual({ type: 'none' });
    expect(run(board, 'A', '')).toEqual({ type: 'none' });
  });

  test('empty board is a no-op', () => {
    expect(run({}, 'A', 'DONE')).toEqual({ type: 'none' });
  });

  test('does not mutate its input', () => {
    const it = items({ A: ['INTAKE', 0], B: ['INTAKE', 1] });
    const snapshot = JSON.stringify(it);
    run(it, 'A', 'B');
    run(it, 'A', 'DONE');
    expect(JSON.stringify(it)).toBe(snapshot);
  });
});
