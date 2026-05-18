import { vi } from 'vitest';

const mockUseSortable = vi.fn(() => ({
  attributes: {},
  listeners: {},
  setNodeRef: vi.fn(),
  transform: null,
  transition: '',
  isDragging: false,
}));

vi.mock('@dnd-kit/sortable', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@dnd-kit/sortable')>();
  return {
    ...actual,
    useSortable: mockUseSortable,
    SortableContext: ({ children }: any) => children,
    verticalListSortingStrategy: {},
  };
});

vi.mock('@dnd-kit/utilities', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@dnd-kit/utilities')>();
  return {
    ...actual,
    CSS: {
      Transform: {
        toString: (transform: any) => {
          if (!transform) return 'none';
          return `translate3d(${transform.x}px, ${transform.y}px, 0)`;
        },
      },
    },
  };
});