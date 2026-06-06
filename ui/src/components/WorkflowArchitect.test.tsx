import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { WorkflowArchitect } from './WorkflowArchitect';
import { LifecyclePhase } from '../types';

describe('WorkflowArchitect', () => {
  const mockOnPhaseChange = vi.fn();

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

  it('renders the correct current phase and goal', () => {
    render(<WorkflowArchitect currentPhase="DISCOVERY" onPhaseChange={mockOnPhaseChange} />);
    
    expect(screen.getByText(/Lifecycle Orchestrator/i)).toBeInTheDocument();
    expect(screen.getByText(/Complete map of affected files and a clear problem statement/i)).toBeInTheDocument();
    expect(screen.getByText(/Context Audit/i)).toBeInTheDocument();
  });

  it('calls onPhaseChange when a phase node is clicked', () => {
    render(<WorkflowArchitect currentPhase="DISCOVERY" onPhaseChange={mockOnPhaseChange} />);
    
    // The second node (BLUEPRINT) is index 2 in the timeline rendering (since the first is 1)
    // We can find it by the text of the phase label
    const blueprintNode = screen.getByText(/BLUEPRINT/i);
    fireEvent.click(blueprintNode);
    
    expect(mockOnPhaseChange).toHaveBeenCalledWith('BLUEPRINT');
  });

  it('displays the correct goal when phase changes to IMPLEMENTATION', () => {
    render(<WorkflowArchitect currentPhase="IMPLEMENTATION" onPhaseChange={mockOnPhaseChange} />);
    
    expect(screen.getByText(/Single, modular, and functional code unit/i)).toBeInTheDocument();
    expect(screen.getByText(/Code Inspection/i)).toBeInTheDocument();
  });

  it('renders the transaction panel with a mock proposal', () => {
    render(<WorkflowArchitect currentPhase="DISCOVERY" onPhaseChange={mockOnPhaseChange} />);
    
    expect(screen.getByText(/Proposed Transaction/i)).toBeInTheDocument();
    expect(screen.getByText(/tx-8821/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Proceed/i })).toBeInTheDocument();
  });
});
