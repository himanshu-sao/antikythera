import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';
import { WorkflowArchitect } from '../WorkflowArchitect';

// Mock fetch to avoid network calls
global.fetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: async () => ({ current_phase: 'DISCOVERY', proposal: null }) } as any)
);

describe('WorkflowArchitect component', () => {
  test('displays the correct goal text for the given phase', () => {
    render(
      <WorkflowArchitect
        itemId="test-item"
        onPhaseChange={() => {}}
        currentPhase="DISCOVERY"
        initialProposal={null}
      />
    );
    // Expect the goal text defined in LIFECYCLE_PIPELINE for DISCOVERY phase to be present
    const goalElement = screen.getByText(/Atomic Task Management & Verification/i);
    expect(goalElement).toBeInTheDocument();
  });
});
