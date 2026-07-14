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
        description: item.description || '',
        status: item.stage,
        order: item.order || 0,
        priority: item.priority || 'Medium',
        complexity: item.complexity || 'complex',
        confidence_score: item.confidence_score || 0,
        comments: item.comments || [],
        history: item.history || [],
        blocked_reason: item.blocked_reason || null,
        assigned_agent: item.assigned_agent || null,
        review_status: item.review_status || 'PENDING',
        created_at: item.created_at || '',
        updated_at: item.updated_at || '',
      }))
      .sort((a, b) => a.order - b.order);

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
    order: input.toIndex,
  };
}
