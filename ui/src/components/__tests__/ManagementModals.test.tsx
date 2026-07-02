import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';
import { BuilderModal } from '../modals/ManagementModals';

// Mock fetch for WorkflowArchitect used inside modal
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: async () => ({
      current_phase: 'DISCOVERY',
      proposal: null,
    }),
  } as any)
);

describe('BuilderModal component', () => {
  test('renders the WorkflowArchitect within the modal', () => {
    const onClose = vi.fn();
    render(<BuilderModal isOpen={true} onClose={onClose} itemId="test-id" />);
    expect(screen.getByText(/Workflow Architect/i)).toBeInTheDocument();
  });
});
