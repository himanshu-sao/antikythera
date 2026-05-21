import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { KanbanColumn, KanbanCard } from './KanbanColumn';

describe('KanbanCard', () => {
  const mockItem = {
    id: 'ID-001',
    title: 'Test automation task',
    priority: 'High',
    confidence_score: 85,
  };

  const mockOnCardClick = vi.fn();

  beforeEach(() => {
    mockOnCardClick.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders card with correct item data', () => {
    render(
      <KanbanCard
        id={mockItem.id}
        title={mockItem.title}
        priority={mockItem.priority}
        confidence_score={mockItem.confidence_score}
        onCardClick={mockOnCardClick}
        onEditClick={vi.fn()}
      />
    );

    expect(screen.getByText(mockItem.id)).toBeInTheDocument();
    expect(screen.getByText(mockItem.title)).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Confidence: 85%')).toBeInTheDocument();
  });

  it('displays correct priority color badge', () => {
    const { container } = render(
      <KanbanCard
        id={mockItem.id}
        title={mockItem.title}
        priority="High"
        confidence_score={85}
        onCardClick={mockOnCardClick}
        onEditClick={vi.fn()}
      />
    );

    const priorityBadge = container.querySelector('.bg-red-100');
    expect(priorityBadge).toBeInTheDocument();
  });

  it('calls onCardClick when card is clicked', () => {
    render(
      <KanbanCard
        id={mockItem.id}
        title={mockItem.title}
        priority={mockItem.priority}
        confidence_score={mockItem.confidence_score}
        onCardClick={mockOnCardClick}
        onEditClick={vi.fn()}
      />
    );

    const card = screen.getByRole('button', { name: /ID-001/i }) || screen.getByText(mockItem.id).closest('div');
    if (card) {
      fireEvent.click(card);
      expect(mockOnCardClick).toHaveBeenCalledWith('ID-001');
    }
  });

  it('renders with different priority levels', () => {
    const priorities = ['High', 'Medium', 'Low'];
    
    priorities.forEach((priority) => {
      cleanup();
      render(
        <KanbanCard
          id="ID-002"
          title="Test"
          priority={priority}
          confidence_score={50}
          onCardClick={mockOnCardClick}
          onEditClick={vi.fn()}
        />
      );
      
      expect(screen.getByText(priority)).toBeInTheDocument();
    });
  });
});

describe('KanbanColumn', () => {
  const mockItems = [
    {
      id: 'ID-001',
      title: 'First task',
      priority: 'High',
      confidence_score: 90,
    },
    {
      id: 'ID-002',
      title: 'Second task',
      priority: 'Medium',
      confidence_score: 75,
    },
  ];

  const mockOnCardClick = vi.fn();

  it('renders column with correct title and item count', () => {
    render(
      <KanbanColumn
        id="REVIEW_SPEC"
        items={mockItems}
        onCardClick={mockOnCardClick}
        onEditClick={vi.fn()}
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
        onEditClick={vi.fn()}
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
        onEditClick={vi.fn()}
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
        onEditClick={vi.fn()}
      />
    );

    const firstCard = screen.getByText('ID-001').closest('div');
    if (firstCard) {
      fireEvent.click(firstCard);
      expect(mockOnCardClick).toHaveBeenCalledWith('ID-001');
    }
  });
});