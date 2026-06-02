import { render, screen } from '@testing-library/react';
import { expect, describe, it, vi } from 'vitest';
import { ArtifactViewer } from '../components/ArtifactViewer';
import { apiUrl } from '../config';

// Mocking dependencies that might cause issues in jsdom
vi.mock('../config', () => ({
  apiUrl: 'http://localhost:3000'
}));

vi.mock('./artifacts/Mermaid', () => ({
  Mermaid: () => <div data-testid="mermaid-chart">Mermaid Chart</div>
}));

vi.mock('./artifacts/Timeline', () => ({
  Timeline: () => <div data-testid="timeline">Timeline</div>
}));

vi.mock('./artifacts/ReviewForm', () => ({
  ReviewForm: () => <div data-testid="review-form">Review Form</div>
}));

describe('ArtifactViewer', () => {
  const mockOnClose = vi.fn();
  const itemId = 'TEST-ITEM';

  it('renders loading state initially', async () => {
    // Mock fetch to hang (never resolves)
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    
    render(<ArtifactViewer itemId={itemId} onClose={mockOnClose} />);
    
    expect(screen.getByText(/Loading artifacts.../i)).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    // Mock fetch to fail
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('API Error'))));
    
    render(<ArtifactViewer itemId={itemId} onClose={mockOnClose} />);
    
    // Need to wait for the async effect to trigger error state. 
    // Using a more flexible regex to handle different error messages or whitespace.
    const errorMsg = await screen.findByText(/Error:/i);
    expect(errorMsg).toBeInTheDocument();
  });

  it('renders empty state when no artifacts are found', async () => {
    // Mock successful but empty response
    50|    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: any) => {
    51|      const urlStr = typeof url === 'string' ? url : url.toString();
    52|      if (urlStr.includes('/api/item/TEST-ITEM/artifact/')) {
    53|        return Promise.resolve({
    54|          ok: false, // No artifacts found
    55|          text: async () => '',
    56|        } as Response);
    57|      }
    58|      if (urlStr.includes('/api/item/TEST-ITEM')) {
    59|        return Promise.resolve({
    60|          ok: true,
    61|          json: async () => ({ id: 'TEST-ITEM', stage: 'DEFAULT', priority: 'low' }),
    62|        } as Response);
    63|      }
    64|      return Promise.reject(new Error('Unknown URL'));
    65|    }));

    render(<ArtifactViewer itemId={itemId} onClose={mockOnClose} />);
    
    // Based on the component output, it renders "Error: No artifacts found"
    const emptyMsg = await screen.findByText(/No artifacts found/i);
    expect(emptyMsg).toBeInTheDocument();
  });
});
