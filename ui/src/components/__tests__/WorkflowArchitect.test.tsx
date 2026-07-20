import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, beforeEach, afterEach } from 'vitest';
import { WorkflowArchitect, nextPhase } from '../WorkflowArchitect';
import { LIFECYCLE_PIPELINE } from '../../types';

// Helper: build a fake fetch Response.
const jsonRes = (body: unknown, ok = true) => ({
  ok,
  json: async () => body,
});

describe('nextPhase helper', () => {
  test('returns the next phase for non-terminal phases and null at HANDOVER', () => {
    expect(nextPhase('DISCOVERY')).toBe('BLUEPRINT');
    expect(nextPhase('BLUEPRINT')).toBe('IMPLEMENTATION');
    expect(nextPhase('HANDOVER')).toBeNull();
  });

  test('returns null for unknown phases', () => {
    // @ts-expect-error: intentionally invalid phase
    expect(nextPhase('NOPE')).toBeNull();
  });
});

describe('WorkflowArchitect component', () => {
  const mockedFetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: a GET /api/orchestrator/<id> returning no active proposal.
    mockedFetch.mockResolvedValue(jsonRes({ current_phase: 'DISCOVERY', proposal: null }));
    (globalThis as any).fetch = mockedFetch;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders the phase timeline and highlights the current phase', async () => {
    render(
      <WorkflowArchitect
        itemId="item-1"
        onPhaseChange={() => {}}
        currentPhase="BLUEPRINT"
        initialProposal={null}
      />
    );
    // The current-phase goal text (from LIFECYCLE_PIPELINE BLUEPRINT) renders.
    expect(
      screen.getByText(/Signed-off interface, spec, or component/i)
    ).toBeInTheDocument();
    // Timeline labels exist for every phase.
    LIFECYCLE_PIPELINE.forEach((p) => {
      expect(
        screen.getByText(p.phase.replace('_', ' '))
      ).toBeInTheDocument();
    });
  });

  test('renders the empty-proposal state when no proposal is present', async () => {
    render(
      <WorkflowArchitect
        itemId="item-2"
        onPhaseChange={() => {}}
        currentPhase="DISCOVERY"
        initialProposal={null}
      />
    );
    expect(
      screen.getByText(/No active transaction proposal/i)
    ).toBeInTheDocument();
    // Proceed is disabled in the empty state (TransactionPanel contract).
    expect(screen.getByRole('button', { name: /^Proceed$/ })).toBeDisabled();
  });

  test('renders an active proposal when one is returned and fires transition on phase click', async () => {
    // First fetch returns an active proposal at BLUEPRINT.
    mockedFetch.mockResolvedValueOnce(
      jsonRes({
        current_phase: 'BLUEPRINT',
        proposal: { id: 'tx-1', description: 'Draft interface contract' },
      })
    );
    // Subsequent transition POST returns success.
    mockedFetch.mockResolvedValueOnce(jsonRes({ status: 'success', new_phase: 'IMPLEMENTATION' }));
    // Any follow-up poll.
    mockedFetch.mockResolvedValue(jsonRes({ current_phase: 'IMPLEMENTATION', proposal: null }));

    const onPhaseChange = vi.fn();
    render(
      <WorkflowArchitect
        itemId="item-3"
        onPhaseChange={onPhaseChange}
        currentPhase="BLUEPRINT"
        initialProposal={null}
      />
    );

    // Active proposal text appears once the poll resolves.
    const proposalText = await screen.findByText(/Draft interface contract/i);
    expect(proposalText).toBeInTheDocument();

    // Click the IMPLEMENTATION phase label to advance.
    const implLabel = screen.getByText('IMPLEMENTATION');
    await act(async () => {
      fireEvent.click(implLabel);
    });

    expect(onPhaseChange).toHaveBeenCalledWith('IMPLEMENTATION');
    const transitionCall = mockedFetch.mock.calls.find(
      ([url]) => typeof url === 'string' && url.includes('/api/orchestrator/transition')
    );
    expect(transitionCall).toBeDefined();
    expect(transitionCall![1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ item_id: 'item-3', target_phase: 'IMPLEMENTATION' }),
    });
  });

  test('Proceed advances to the next lifecycle phase', async () => {
    // Initial poll: DISCOVERY with an active proposal so Proceed is enabled.
    mockedFetch.mockResolvedValueOnce(
      jsonRes({
        current_phase: 'DISCOVERY',
        proposal: { id: 'tx-2', description: 'Propose discovery scope' },
      })
    );
    // Proceed triggers transition -> BLUEPRINT.
    mockedFetch.mockResolvedValueOnce(jsonRes({ status: 'success', new_phase: 'BLUEPRINT' }));
    mockedFetch.mockResolvedValue(jsonRes({ current_phase: 'BLUEPRINT', proposal: null }));

    const onPhaseChange = vi.fn();
    render(
      <WorkflowArchitect
        itemId="item-4"
        onPhaseChange={onPhaseChange}
        currentPhase="DISCOVERY"
        initialProposal={null}
      />
    );

    // Wait for the active proposal (Proceed button becomes the enabled variant).
    await screen.findByText(/Propose discovery scope/i);
    const proceedBtn = screen.getByRole('button', { name: /^Proceed$/ });
    expect(proceedBtn).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(proceedBtn);
    });

    expect(onPhaseChange).toHaveBeenCalledWith('BLUEPRINT');
  });

  test('Proceed at terminal HANDOVER phase does not advance', async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonRes({
        current_phase: 'HANDOVER',
        proposal: { id: 'tx-3', description: 'Final handover package' },
      })
    );
    mockedFetch.mockResolvedValue(jsonRes({ current_phase: 'HANDOVER', proposal: { id: 'tx-3', description: 'Final handover package' } }));

    const onPhaseChange = vi.fn();
    render(
      <WorkflowArchitect
        itemId="item-5"
        onPhaseChange={onPhaseChange}
        currentPhase="HANDOVER"
        initialProposal={null}
      />
    );

    await screen.findByText(/Final handover package/i);
    const proceedBtn = screen.getByRole('button', { name: /^Proceed$/ });
    // Proceed is enabled (there IS a proposal) but is a no-op at the terminal phase.
    expect(proceedBtn).not.toBeDisabled();

    const callsBefore = mockedFetch.mock.calls.length;
    await act(async () => {
      fireEvent.click(proceedBtn);
    });

    // No transition call fired — onPhaseChange must NOT have been called.
    expect(onPhaseChange).not.toHaveBeenCalled();
    const transitionCall = mockedFetch.mock.calls
      .slice(callsBefore)
      .find(([url]) => typeof url === 'string' && url.includes('/api/orchestrator/transition'));
    expect(transitionCall).toBeUndefined();
  });

  test('a rejected fetch does not crash and the poll interval is cleared on unmount', async () => {
    vi.useFakeTimers();
    mockedFetch.mockRejectedValue(new Error('network down'));

    const { unmount } = render(
      <WorkflowArchitect
        itemId="item-6"
        onPhaseChange={() => {}}
        currentPhase="DISCOVERY"
        initialProposal={null}
      />
    );

    // Advance the fake clock past several poll intervals; fetch rejects but no throw.
    await act(async () => {
      vi.advanceTimersByTimeAsync(15000);
    });

    // Component still mounted and functional (goal text present).
    expect(
      screen.getByText(/Context Audit/i)
    ).toBeInTheDocument();

    const callsBeforeUnmount = mockedFetch.mock.calls.length;
    unmount();

    // After unmount, further timer ticks must NOT trigger more fetches.
    await act(async () => {
      vi.advanceTimersByTimeAsync(15000);
    });
    expect(mockedFetch.mock.calls.length).toBe(callsBeforeUnmount);
  });
});
