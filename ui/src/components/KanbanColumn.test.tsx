import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { KanbanColumn, KanbanCardContent } from './KanbanColumn';

describe('KanbanCardContent', () => {
  const mockItem = {
    id: 'ID-001',
    title: 'Test automation task',
    priority: 'High',
    confidence_score: 85,
    stage: 'INTAKE',
    updated_at: '2026-05-20T10:00:00Z',
    source_type: 'file',
    source_value: 'test.md',
  };

  const mockOnCardClick = vi.fn();
  const mockOnEditClick = vi.fn();
  const mockOnDeleteClick = vi.fn();

  beforeEach(() => {
    mockOnCardClick.mockClear();
    mockOnEditClick.mockClear();
    mockOnDeleteClick.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders card with correct item data', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    expect(screen.getByText(mockItem.id)).toBeInTheDocument();
    expect(screen.getByText(mockItem.title)).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText(/85%/)).toBeInTheDocument();
    expect(screen.getByText(/5\/20\/2026/i)).toBeInTheDocument();
  });

  it('displays correct priority color badge for High priority', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    const badge = screen.getByText(mockItem.priority);
    expect(badge).toBeInTheDocument();
    
    // Check if the badge has the expected Tailwind class
    expect(badge.className).toContain('bg-[#f8ead8]');
    expect(badge.className).toContain('text-[#a45a12]');
  });

  it('calls onCardClick when card is clicked', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    const card = screen.getByText(mockItem.id).closest('div');
    if (card) {
      fireEvent.click(card);
      expect(mockOnCardClick).toHaveBeenCalledWith(mockItem.id);
    }
  });

  it('renders error state when blocked_reason is provided', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        blocked_reason="Validation failed"
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    expect(screen.getByText(/Error: Validation failed/i)).toBeInTheDocument();
  });

  it('renders action required badge for REVIEW_ stages', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        stage="REVIEW_SPEC"
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    expect(screen.getByText(/ACTION REQUIRED/i)).toBeInTheDocument();
  });

  it('renders agent working status for EXECUTING stage', () => {
    render(
      <KanbanCardContent
        {...mockItem}
        stage="EXECUTING"
        latestStatus="Analyzing requirements..."
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
      />
    );

    expect(screen.getByText(/Analyzing requirements.../i)).toBeInTheDocument();
  });
});

describe('KanbanColumn', () => {
  const mockItems = [
    {
      id: 'ID-001',
      title: 'First task',
      priority: 'High',
      confidence_score: 90,
      stage: 'REVIEW_SPEC',
      updated_at: '2026-05-20T10:00:00Z',
    },
    {
      id: 'ID-002',
      title: 'Second task',
      priority: 'Medium',
      confidence_score: 75,
      stage: 'ARCHITECTURE',
      updated_at: '2026-05-20T10:00:00Z',
    },
  ];

  const mockOnCardClick = vi.fn();
  const mockOnEditClick = vi.fn();
  const mockOnDeleteClick = vi.fn();
  const mockOnFetchLatestStatus = vi.fn();

  it('renders column with correct title and item count', () => {
    render(
      <KanbanColumn
        id="REVIEW_SPEC"
        items={mockItems}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
        onFetchLatestStatus={mockOnFetchLatestStatus}
      />
    );

    expect(screen.getByText(/Review Spec/i)).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('renders all items in the column', () => {
    render(
      <KanbanColumn
        id="REVIEW_SPEC"
        items={mockItems}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
        onFetchLatestStatus={mockOnFetchLatestStatus}
      />
    );

    expect(screen.getByText('ID-001')).toBeInTheDocument();
    expect(screen.getByText('First task')).toBeInTheDocument();
    expect(screen.getByText('ID-002')).toBeInTheDocument();
    expect(screen.getByText('Second task')).toBeInTheDocument();
  });

  it('renders empty column when no items', () => {
    render(
      <KanbanColumn
        id="INTAKE"
        items={[]}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
        onFetchLatestStatus={mockOnFetchLatestStatus}
      />
    );

    expect(screen.getByText(/Intake/i)).toBeInTheDocument();
    expect(screen.getByText('(0)')).toBeInTheDocument();
  });

  it('passes click events to child cards', () => {
    render(
      <KanbanColumn
        id="REVIEW_SPEC"
        items={mockItems}
        onCardClick={mockOnCardClick}
        onEditClick={mockOnEditClick}
        onDeleteClick={mockOnDeleteClick}
        onFetchLatestStatus={mockOnFetchLatestStatus}
      />
    );

    const firstCard = screen.getByText('ID-001').closest('div');
    if (firstCard) {
      fireEvent.click(firstCard);
      expect(mockOnCardClick).toHaveBeenCalledWith('ID-001');
    }
  });
});
