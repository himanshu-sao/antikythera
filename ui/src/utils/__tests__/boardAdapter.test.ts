import { describe, test, expect } from 'vitest';
import { apiToBoardModel } from '../boardAdapter';
import type { PipelineState, BoardColumn, BoardCard } from '../../types/legacy-pipeline';

// Regression guard for the dec #22 / §7 Correction A retarget (T3b): boardAdapter must
// resolve PipelineState / PipelineItem / BoardColumn / BoardCard from legacy-pipeline.ts
// (not the empty ../types). Before the fix the four symbols were undefined and broke the
// board render path the moment a consumer imported boardAdapter.

const state: PipelineState = {
  items: {
    'ID-001': {
      id: 'ID-001',
      title: 'Twistlock bump brotli',
      stage: 'REVIEW_SPEC',
      order: 2,
      priority: 'high',
      complexity: 'complex',
      description: 'Upgrade brotli across services',
      confidence_score: 88,
      comments: [],
      history: [{ stage: 'REFINEMENT', at: '2026-07-20T16:41:35Z', agent: 'refiner' }],
      blocked_reason: null,
      assigned_agent: null,
      review_status: 'PENDING',
      created_at: '2026-07-20T16:41:35.764089Z',
      updated_at: '2026-07-20T16:41:35.764091Z',
    },
    'ID-002': {
      id: 'ID-002',
      title: 'Docs sweep',
      stage: 'INTAKE',
      order: 1,
      priority: 'low',
      description: 'Refresh agent docs',
    },
  },
};

describe('boardAdapter.apiToBoardModel', () => {
  const columns: BoardColumn[] = apiToBoardModel(state);

  test('returns one column per lifecycle stage', () => {
    expect(columns).toHaveLength(10);
    expect(columns.map((c) => c.id)).toEqual([
      'INTAKE', 'REFINEMENT', 'REVIEW_SPEC', 'ARCHITECTURE',
      'REVIEW_ARCH', 'TESTING', 'REVIEW_TEST', 'APPROVED', 'EXECUTING', 'DONE',
    ]);
  });

  test('places items into the column matching their stage', () => {
    const intake = columns.find((c) => c.id === 'INTAKE');
    const review = columns.find((c) => c.id === 'REVIEW_SPEC');
    expect(intake?.cards).toHaveLength(1);
    expect(intake?.cards[0].id).toBe('ID-002');
    expect(review?.cards).toHaveLength(1);
    expect(review?.cards[0].id).toBe('ID-001');
  });

  test('maps every field the board card shape declares, with safe fallbacks', () => {
    const card: BoardCard = columns.find((c) => c.id === 'REVIEW_SPEC')!.cards[0];
    expect(card.title).toBe('Twistlock bump brotli');
    expect(card.status).toBe('REVIEW_SPEC');
    expect(card.order).toBe(2);
    expect(card.priority).toBe('high');
    expect(card.complexity).toBe('complex');
    expect(card.confidence_score).toBe(88);
    expect(card.comments).toEqual([]);
    expect(card.history).toHaveLength(1);
    expect(card.blocked_reason).toBeNull();
    expect(card.assigned_agent).toBeNull();
    expect(card.review_status).toBe('PENDING');
    expect(card.created_at).toBe('2026-07-20T16:41:35.764089Z');
  });

  test('applies fallbacks for fields absent on a sparse item', () => {
    const card: BoardCard = columns.find((c) => c.id === 'INTAKE')!.cards[0];
    expect(card.confidence_score).toBe(0); // absent → 0
    expect(card.complexity).toBe('complex'); // absent → 'complex'
    expect(card.priority).toBe('low'); // truthy value passes through (|| only fills falsy)
    expect(card.comments).toEqual([]); // absent → []
    expect(card.history).toEqual([]); // absent → []
    expect(card.review_status).toBe('PENDING'); // absent → 'PENDING'
    expect(card.blocked_reason).toBeNull(); // absent → null
    expect(card.assigned_agent).toBeNull(); // absent → null
  });

  test('uses "Medium" as the priority fallback only when priority is falsy', () => {
    const sparse: PipelineState = {
      items: {
        z: { id: 'z', title: 'Z', stage: 'INTAKE', order: 0, priority: '' },
      },
    };
    const card: BoardCard = apiToBoardModel(sparse).find((c) => c.id === 'INTAKE')!.cards[0];
    expect(card.priority).toBe('Medium');
  });

  test('sorts cards within a column by order', () => {
    const multi: PipelineState = {
      items: {
        a: { id: 'a', title: 'A', stage: 'INTAKE', order: 3, priority: 'low' },
        b: { id: 'b', title: 'B', stage: 'INTAKE', order: 1, priority: 'low' },
        c: { id: 'c', title: 'C', stage: 'INTAKE', order: 2, priority: 'low' },
      },
    };
    const intake = apiToBoardModel(multi).find((c) => c.id === 'INTAKE');
    expect(intake!.cards.map((c) => c.id)).toEqual(['b', 'c', 'a']);
  });
});
