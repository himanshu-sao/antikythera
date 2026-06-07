1|import React from 'react';
2|import { render, screen } from '@testing-library/react';
3|import '@testing-library/jest-dom';
4|import { BuilderModal } from '../modals/ManagementModals';
5|// Mock fetch for WorkflowArchitect used inside modal
6|global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => ({ current_phase: 'DISCOVERY', proposal: null }) } as any));
7|
8|describe('BuilderModal component', () => {
9|  test('renders the WorkflowArchitect within the modal', () => {
10|    const onClose = jest.fn();
11|    render(<BuilderModal isOpen={true} onClose={onClose} itemId="test-id" />);
12|    // The modal title should be present
13|    expect(screen.getByText(/Workflow Architect/i)).toBeInTheDocument();
14|    // The mock proposal text should appear in the TransactionPanel (via WorkflowArchitect)
15|    // expect(screen.getByText(/Mock plan details/i)).toBeInTheDocument();
16|  });
17|});
18|