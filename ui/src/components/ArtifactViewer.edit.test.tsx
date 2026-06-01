// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ArtifactViewer } from './ArtifactViewer';

describe('ArtifactViewer Editing', () => {
  const mockItemId = 'ID-001';
  
  const mockResponse = (data: any, status = 200) => 
    Promise.resolve(new Response(typeof data === 'string' ? data : JSON.stringify(data), { status }));

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  const createMockFetch = (overrides: any = {}) => {
    return vi.fn(async (input: any, init?: any) => {
      const url = typeof input === 'string' ? input : input.url;
      const method = init?.method || 'GET';
      const cleanUrl = url.replace('http://localhost:8006', '').replace('http://localhost:8000', '');

      // 1. Fetch Item Details
      if (cleanUrl.includes(`/api/item/${mockItemId}`) && method === 'GET' && !cleanUrl.includes('/artifact/') && !cleanUrl.includes('/timeline')) {
        return mockResponse(overrides.itemDetails || { id: mockItemId, name: 'Test Item', stage: 'REVIEW_SPEC' });
      }
      
      // 2. Fetch Individual Artifacts
      if (cleanUrl.includes(`/api/item/${mockItemId}/artifact/`) && method === 'GET') {
        if (cleanUrl.includes('review.md')) return mockResponse(overrides.reviewContent || 'initial review content');
        if (cleanUrl.includes('spec.md')) return mockResponse(overrides.specContent || 'spec content');
        if (cleanUrl.includes('architecture.md')) return mockResponse(overrides.archContent || 'arch content');
        if (cleanUrl.includes('tests.md')) return mockResponse(overrides.testsContent || 'tests content');
      }
      
      // 3. Timeline
      if (cleanUrl.includes(`/api/item/${mockItemId}/timeline`)) {
        return mockResponse([]);
      }

      // 4. Move Item (Stage transition)
      if (cleanUrl.includes('/api/move') && method === 'POST') {
        return mockResponse({ status: 'success' });
      }

      // 5. Save Content (POST)
      if (cleanUrl.includes(`/api/item/${mockItemId}/artifact/`) && method === 'POST') {
        if (overrides.failSave && cleanUrl.includes('review.md')) {
          return Promise.reject(new Error('Network Error'));
        }
        // For generic artifacts, fail if failSave is true
        if (overrides.failSave && !cleanUrl.includes('review.md')) {
          return Promise.reject(new Error('Network Error'));
        }
        return mockResponse({ status: 'success' });
      }
      
      return Promise.reject(new Error('Not Found'));
    });
  };

  it('allows editing of review.md and triggers save API', async () => {
    global.fetch = createMockFetch();

    render(<ArtifactViewer itemId={mockItemId} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('review.md')).toBeInTheDocument();
    }, { timeout: 3000 });

    await act(async () => {
      fireEvent.click(screen.getByText('review.md'));
    });

    // Target the button specifically by role to avoid conflict with the heading
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /submit review/i })).toBeInTheDocument();
    });

    await act(async () => {
      const commentsField = screen.getByLabelText('Comments');
      fireEvent.change(commentsField, { target: { value: 'Good work' } });
      fireEvent.click(screen.getByRole('button', { name: /submit review/i }));
    });

    await new Promise(r => setTimeout(r, 1100));

    const saveCall = (global.fetch as any).mock.calls.find((call: any) => 
      call[0].includes(`/api/item/${mockItemId}/artifact/review.md/content`) && call[1]?.method === 'POST'
    );
    expect(saveCall).toBeDefined();
  });

  it('debounces multiple changes to a single API call', async () => {
    global.fetch = createMockFetch({
      itemDetails: { id: mockItemId, name: 'Test Item', stage: 'DEFAULT' }
    });

    render(<ArtifactViewer itemId={mockItemId} onClose={() => {}} />);
    
    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('spec.md'));
    });
    
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Edit'));
    });

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    await act(async () => {
      const editor = screen.getByRole('textbox');
      for (let i = 0; i < 5; i++) {
        fireEvent.change(editor, { target: { value: `change ${i}` } });
      }
    });

    await new Promise(r => setTimeout(r, 1100));

    const postCalls = (global.fetch as any).mock.calls.filter((call: any) => call[1]?.method === 'POST');
    expect(postCalls).toHaveLength(1);
  });

  it('handles save API failures gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    global.fetch = createMockFetch({ failSave: true });

    render(<ArtifactViewer itemId={mockItemId} onClose={() => {}} />);
    
    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('spec.md'));
    });
    
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Edit'));
    });

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    await act(async () => {
      const editor = screen.getByRole('textbox');
      fireEvent.change(editor, { target: { value: 'trigger error' } });
    });

    await new Promise(r => setTimeout(r, 1100));

    await waitFor(() => {
      // Filter out "act" warnings from the spy calls to find the real error
      const hasSaveError = consoleSpy.mock.calls.some(call => 
        call[0]?.includes('Save error:')
      );
      expect(hasSaveError).toBe(true);
    });

    consoleSpy.mockRestore();
  });
});
