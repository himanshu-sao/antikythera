import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ArtifactViewer } from './ArtifactViewer';

// Mock lodash debounce to synchronize with Vitest fake timers cleanly
vi.mock('lodash', () => ({
  debounce: (fn: any, delay: number) => {
    let timeoutId: any;
    const debounced = (...args: any[]) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
    debounced.cancel = () => clearTimeout(timeoutId);
    return debounced;
  }
}));

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

    // Load initial artifacts (flush sequential fetches in loop)
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(0);
    }

    expect(screen.getByText('review.md')).toBeInTheDocument();

    fireEvent.click(screen.getByText('review.md'));

    const textarea = screen.getByPlaceholderText(/Write your review here.../i);
    fireEvent.change(textarea, { target: { value: 'Updated review content' } });

    // Advance timers by 1000ms to trigger the debounced saveContent
    await vi.advanceTimersByTimeAsync(1000);

    expect(screen.getByText(/Saving.../i)).toBeInTheDocument();

    // Complete the save fetch call
    await vi.advanceTimersByTimeAsync(0);

    const calls = vi.mocked(global.fetch).mock.calls;
    const saveCall = calls.find(call => call[1]?.method === 'POST');
    expect(saveCall).toBeDefined();
    const body = JSON.parse(saveCall[1].body);
    expect(body.content).toBe('Updated review content');

    expect(screen.getByText(/Saved/i)).toBeInTheDocument();
  });

  it('debounces multiple changes to a single API call', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url, options) => {
      if (options?.method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify({ status: 'success' }), { status: 200 }));
      }
      if (url.includes('/artifact/review.md')) {
        return Promise.resolve(new Response(mockArtifacts[0].content, { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(mockArtifacts), { status: 200 }));
    });

    render(<ArtifactViewer itemId="ID-001" onClose={() => {}} />);
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(0);
    }
    expect(screen.getByText('review.md')).toBeInTheDocument();
    fireEvent.click(screen.getByText('review.md'));

    const textarea = screen.getByPlaceholderText(/Write your review here.../i);

    // Rapid fire changes
    fireEvent.change(textarea, { target: { value: 'Change 1' } });
    fireEvent.change(textarea, { target: { value: 'Change 2' } });
    fireEvent.change(textarea, { target: { value: 'Final Change' } });

    // Advance time to trigger debounce
    await vi.advanceTimersByTimeAsync(1000);

    // Flush async fetch
    await vi.advanceTimersByTimeAsync(0);

    const postCalls = vi.mocked(global.fetch).mock.calls.filter(call => call[1]?.method === 'POST');
    expect(postCalls).toHaveLength(1);
    const body = JSON.parse(postCalls[0][1].body);
    expect(body.content).toBe('Final Change');
  });

  it('handles save API failures gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(global, 'fetch').mockImplementation((url, options) => {
      if (options?.method === 'POST') {
        return Promise.resolve(new Response(null, { status: 500 }));
      }
      if (url.includes('/artifact/review.md')) {
        return Promise.resolve(new Response(mockArtifacts[0].content, { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(mockArtifacts), { status: 200 }));
    });

    render(<ArtifactViewer itemId="ID-001" onClose={() => {}} />);
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(0);
    }
    expect(screen.getByText('review.md')).toBeInTheDocument();
    fireEvent.click(screen.getByText('review.md'));

    const textarea = screen.getByPlaceholderText(/Write your review here.../i);
    fireEvent.change(textarea, { target: { value: 'Failed content' } });

    // Advance time to trigger debounce
    await vi.advanceTimersByTimeAsync(1000);

    // Flush async fetch
    await vi.advanceTimersByTimeAsync(0);

    expect(consoleSpy).toHaveBeenCalledWith('Save error:', expect.any(Error));

    consoleSpy.mockRestore();
  });
});
