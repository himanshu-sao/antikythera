import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BuilderModal } from '../modals/ManagementModals';

// Mock fetch for WorkflowArchitect used inside modal
global.fetch = jest.fn(() =>
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
    const onClose = jest.fn();
    render(<BuilderModal isOpen={true} onClose={onClose} itemId="test-id" />);
    expect(screen.getByText(/Workflow Architect/i)).toBeInTheDocument();
  });
});
