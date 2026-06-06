import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { BuilderModal } from './ManagementModals';

describe('BuilderModal Integration', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/orchestrator/transition')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'success' }),
        } as Response);
      }
      if (url.includes('/api/orchestrator/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            current_phase: 'DISCOVERY',
            proposal: {
              id: 'tx-8821',
              status: 'PROPOSED',
              context: ['file1.txt', 'file2.txt'],
              plan: 'Mock plan details',
              verification: 'Mock verification details'
            }
          }),
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL: ' + url));
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });
  it('updates the WorkflowArchitect goal when the phase is changed via the timeline', () => {
    render(<BuilderModal isOpen={true} onClose={vi.fn()} />);
    
    // 1. Verify initial state (DISCOVERY)
    expect(screen.getByText(/Complete map of affected files/i)).toBeInTheDocument();
    
    // 2. Click the BLUEPRINT node (Node 2)
    const blueprintNode = screen.getByText(/BLUEPRINT/i);
    fireEvent.click(blueprintNode);
    
    // 3. Verify that the Goal updated to the Blueprint goal
    expect(screen.getByText(/Signed-off interface, spec, or component tree/i)).toBeInTheDocument();
    expect(screen.queryByText(/Complete map of affected files/i)).not.toBeInTheDocument();
  });

  it('renders the Transaction Panel within the BuilderModal', () => {
    render(<BuilderModal isOpen={true} onClose={vi.fn()} />);
    
    expect(screen.getByText(/Proposed Transaction/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Proceed/i })).toBeInTheDocument();
  });
});
