import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ArtifactViewer } from './ArtifactViewer';

const mockArtifacts = [
  {
    name: 'review.md',
    content: 'Initial review content',
    type: 'review',
  },
];

describe('ArtifactViewer Editing', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('allows editing of review.md and triggers save API', async () => {
    // Mock the initial fetch of artifacts
    vi.spyOn(global, 'fetch').mockImplementation((url, options) => {
      if (options?.method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify({ status: 'success' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }));
      }

      if (url.includes('/artifact/review.md')) {
        return Promise.resolve(new Response(mockArtifacts[0].content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }

      return Promise.resolve(new Response(JSON.stringify(mockArtifacts), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('review.md')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('review.md'));

    const textarea = screen.getByPlaceholderText(/Write your review here.../i);
    fireEvent.change(textarea, { target: { value: 'Updated review content' } });

    // Advance timers to trigger debounce
    vi.advanceTimersByTime(100);

    await waitFor(() => {
      expect(screen.getByText(/Saving.../i)).toBeInTheDocument();
    });

    // Advance timers to complete the save
    vi.advanceTimersByTime(1000);

    // Since fetch is async, we need to allow the promise to resolve
    await vi.runAllTimersAsync();

    await waitFor(() => {
      const calls = vi.mocked(global.fetch).mock.calls;
      const saveCall = calls.find(call => call[1]?.method === 'POST');
      expect(saveCall).toBeDefined();
      const body = JSON.parse(saveCall[1].body);
      expect(body.content).toBe('Updated review content');
    });

    await waitFor(() => {
      expect(screen.getByText(/Saved/i)).toBeInTheDocument();
    });
  });
});
