import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';
import App from '../../App';

// Mock fetch globally for the App component
const fetchMock = vi.fn()
  .mockImplementationOnce(() => // First call: /api/state
    Promise.resolve({
      ok: true,
      json: async () => ({
        items: {},
        stages: ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]
      })
    } as any)
  )
  .mockImplementationOnce(() => // Second call: /api/pipelines
    Promise.resolve({
      ok: true,
      json: async () => ([])
    } as any)
  )
  .mockImplementation(() => // Subsequent calls
    Promise.resolve({
      ok: true,
      json: async () => ([])
    } as any)
  );

global.fetch = fetchMock as any;

describe('App polling behavior', () => {
  test('fetch is called at least once on render', async () => {
    render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
