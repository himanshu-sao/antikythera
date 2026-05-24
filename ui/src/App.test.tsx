import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';
import type { PipelineState, KanbanCardData } from './types';

// Mock @dnd-kit/core and @dnd-kit/sortable
vi.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd }: { children: React.ReactNode; onDragEnd: (event: { active: { id: string }; over: { id: string } | null }) => void }) => {
    // Expose onDragEnd for testing
    (window as Record<string, unknown>).__dndOnDragEnd = onDragEnd;
    return <div data-testid="dnd-context">{children}</div>;
  },
  closestCorners: vi.fn(),
  KeyboardSensor: vi.fn(),
  PointerSensor: vi.fn(),
  useSensor: vi.fn(() => ({})),
  useSensors: vi.fn(() => [{}]),
  DragEndEvent: vi.fn(),
}));

vi.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <div data-testid="sortable-context">{children}</div>,
  sortableKeyboardCoordinates: vi.fn(),
}));

vi.mock('./components/KanbanColumn', () => ({
  KanbanColumn: ({ id, items, onCardClick }: { id: string; items: KanbanCardData[]; onCardClick: (id: string) => void }) => (
    <div data-testid={`column-${id}`}>
      <span>{id}</span>
      <span data-testid={`column-count-${id}`}>{items.length}</span>
      {items.map((item: KanbanCardData) => (
        <div key={item.id} data-testid={`card-${item.id}`} onClick={() => onCardClick(item.id)}>
          {item.id} - {item.title}
        </div>
      ))}
    </div>
  ),
}));

vi.mock('./components/ArtifactViewer', () => ({
  ArtifactViewer: ({ itemId, onClose }: { itemId: string; onClose: () => void }) => (
    <div data-testid="artifact-viewer">
      <span>{itemId}</span>
      <button onClick={onClose} data-testid="close-viewer">Close</button>
    </div>
  ),
}));

const mockState: PipelineState = {
  items: {
    'ID-001': {
      id: 'ID-001',
      title: 'Test task one',
      priority: 'High',
      stage: 'INTAKE',
      confidence_score: 85,
      updated_at: '2026-05-15T00:00:00Z',
    },
    'ID-002': {
      id: 'ID-002',
      title: 'Test task two',
      priority: 'Medium',
      stage: 'REVIEW_SPEC',
      confidence_score: 70,
      updated_at: '2026-05-15T00:00:00Z',
    },
    'ID-003': {
      id: 'ID-003',
      title: 'Test task three',
      priority: 'Low',
      stage: 'REVIEW_SPEC',
      confidence_score: 90,
      updated_at: '2026-05-15T00:00:00Z',
    },
  },
};

describe('App drag-and-drop handleDragEnd', () => {
  let mockFetch: any;

  beforeEach(() => {
    vi.clearAllMocks();
    (window as Record<string, unknown>).__dndOnDragEnd = undefined;

    // Use a dynamic mock implementation that handles state requests and move requests robustly
    mockFetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/state')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockState,
        } as Response);
      }
      if (url.includes('/api/move')) {
        return Promise.resolve({
          ok: true,
        } as Response);
      }
      return Promise.resolve({
        ok: true,
      } as Response);
    });

    vi.spyOn(global, 'fetch').mockImplementation(mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders all stages and items from state', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
      expect(screen.getByTestId('column-REVIEW_SPEC')).toBeInTheDocument();
    });

    expect(screen.getByTestId('column-count-INTAKE').textContent).toBe('1');
    expect(screen.getByTestId('column-count-REVIEW_SPEC').textContent).toBe('2');
  });

  it('handleDragEnd moves item to a column when dropped on column header', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    // Simulate drag end: drop ID-001 onto REVIEW_SPEC column
    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    await handleDragEnd!({
      active: { id: 'ID-001' },
      over: { id: 'REVIEW_SPEC' },
    });

    // Should call move API with new stage and order 2 (there are already 2 items in REVIEW_SPEC column)
    const moveCall = mockFetch.mock.calls.find(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCall).toBeDefined();
    expect((moveCall as unknown[])[1]).toMatchObject({
      method: 'POST',
    });
    expect(JSON.parse((moveCall as unknown[])[1].body as string)).toEqual({
      item_id: 'ID-001',
      new_stage: 'REVIEW_SPEC',
      order: 2,
    });
  });

  it('handleDragEnd moves item to another item\'s stage when dropped on a card', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    // Simulate drag end: drop ID-001 (INTAKE) onto ID-002 (REVIEW_SPEC)
    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    await handleDragEnd!({
      active: { id: 'ID-001' },
      over: { id: 'ID-002' },
    });

    // Should call move API with REVIEW_SPEC (ID-002's stage) and order 0
    const moveCall = mockFetch.mock.calls.find(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCall).toBeDefined();
    expect((moveCall as unknown[])[1]).toMatchObject({
      method: 'POST',
    });
    expect(JSON.parse((moveCall as unknown[])[1].body as string)).toEqual({
      item_id: 'ID-001',
      new_stage: 'REVIEW_SPEC',
      order: 0,
    });
  });

  it('handleDragEnd does nothing when dropped on same stage', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    // Simulate drag end: drop ID-001 onto INTAKE column (same stage)
    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    await handleDragEnd!({
      active: { id: 'ID-001' },
      over: { id: 'INTAKE' },
    });

    // Should NOT call move API (same stage)
    const moveCalls = mockFetch.mock.calls.filter(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCalls.length).toBe(0);
  });

  it('handleDragEnd does nothing when over is null', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    await handleDragEnd!({
      active: { id: 'ID-001' },
      over: null,
    });

    const moveCalls = mockFetch.mock.calls.filter(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCalls.length).toBe(0);
  });

  it('handleDragEnd does nothing when active item does not exist in state', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    await handleDragEnd!({
      active: { id: 'ID-NONEXISTENT' },
      over: { id: 'REVIEW_SPEC' },
    });

    const moveCalls = mockFetch.mock.calls.filter(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCalls.length).toBe(0);
  });

  it('handleDragEnd uses state.items[overId]?.stage for card-to-card drop', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('column-INTAKE')).toBeInTheDocument();
    });

    const handleDragEnd = (window as Record<string, unknown>).__dndOnDragEnd as ((event: { active: { id: string }; over: { id: string } | null }) => void) | undefined;
    expect(handleDragEnd).toBeDefined();

    // Drop ID-001 (INTAKE) onto ID-003 (REVIEW_SPEC)
    await handleDragEnd!({
      active: { id: 'ID-001' },
      over: { id: 'ID-003' },
    });

    // Verify the move API was called with REVIEW_SPEC (ID-003's stage) and order 1
    const moveCall = mockFetch.mock.calls.find(
      (call: unknown[]) => call[0] === 'http://localhost:8000/api/move'
    );
    expect(moveCall).toBeDefined();
    expect(JSON.parse((moveCall as unknown[])[1].body as string)).toEqual({
      item_id: 'ID-001',
      new_stage: 'REVIEW_SPEC',
      order: 1,
    });
  });
});