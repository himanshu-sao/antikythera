import { PipelineState, PipelineItem, BoardColumn, BoardCard } from '../types';

export function apiToBoardModel(state: PipelineState): BoardColumn[] {
  const stages = [
    "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
    "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
  ];

  return stages.map((stage, index) => {
    const cards = Object.entries(state.items)
      .filter(([_, item]) => item.stage === stage)
      .map(([id, item]) => ({
        id,
        title: item.title,
        description: '', // Backend doesn't have this yet
        status: item.stage,
        order: 0, // Backend doesn't have this yet
        priority: item.priority || 'Medium',
        confidence_score: item.confidence_score || 0,
        comments: [], // Backend doesn't have this yet
      }));

    return {
      id: stage,
      title: stage.replace('_', ' '),
      order: index,
      cards: cards,
    };
  });
}

export function boardCreatePayload(input: { id: string; title: string }) {
  return {
    item_id: input.id,
    title: input.title,
  };
}

export function boardMovePayload(input: {
  cardId: string;
  fromColumnId: string;
  toColumnId: string;
  toIndex: number;
}) {
  return {
    item_id: input.cardId,
    new_stage: input.toColumnId,
  };
}
