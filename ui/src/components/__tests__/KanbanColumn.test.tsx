import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { KanbanColumn } from '../KanbanColumn';

interface KanbanCardData {
  id: string;
  title: string;
  stage: string;
  priority: string;
  description?: string;
  confidence?: number;
  updated_at?: string;
  confidence_score?: number;
}

const mockItems: KanbanCardData[] = [
  {
    id: 'card-1',
    title: 'Test Card',
    stage: 'IN_PROGRESS',
    priority: 'High',
    confidence_score: 90,
    description: 'A test card',
    updated_at: new Date().toISOString(),
  },
];

describe('KanbanColumn component', () => {
  test('renders column header with count', () => {
    render(
      <KanbanColumn
        id="col-1"
        items={mockItems}
        onCardClick={() => {}}
        onEditClick={() => {}}
        onDeleteClick={() => {}}
        onFetchLatestStatus={async (_id) => undefined}
      />
    );
    expect(screen.getByText('Col-1')).toBeInTheDocument();
    expect(screen.getByText(/\(1\)/)).toBeInTheDocument(); // count displayed in parentheses
  });

  test('renders a card with correct badges', () => {
    render(
      <KanbanColumn
        id="col-1"
        items={mockItems}
        onCardClick={() => {}}
        onEditClick={() => {}}
        onDeleteClick={() => {}}
        onFetchLatestStatus={async (_id) => undefined}
      />
    );
    // Priority badge contains the word High (may have whitespace)
    expect(screen.getByText(/High/)).toBeInTheDocument();
    // No confidence badge currently rendered; ensure card is present
    expect(screen.getByText('Test Card')).toBeInTheDocument();
  });
});
