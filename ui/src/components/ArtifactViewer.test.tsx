import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ArtifactViewer } from './ArtifactViewer';

const mockArtifacts = [
  {
    name: 'spec.md',
    content: '# Specification\n\nThis is the specification document.',
    type: 'spec',
  },
  {
    name: 'architecture.md',
    content: '# Architecture\n\nSystem architecture details.',
    type: 'architecture',
  },
  {
    name: 'tests.md',
    content: '# Tests\n\nTest plan and cases.',
    type: 'tests',
  },
];

describe('ArtifactViewer', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading state initially', () => {
    vi.spyOn(global, 'fetch').mockImplementation(() => 
      new Promise(() => {}) // Never resolves
    );

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText(/Loading artifacts/i)).toBeInTheDocument();
  });

  it('fetches artifacts on mount', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const artifactName = url.split('/').pop();
      const artifact = mockArtifacts.find(a => a.name === artifactName);
      if (artifact) {
        return Promise.resolve(new Response(artifact.content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
    });
  });

  it('displays all artifact names in the sidebar', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const artifactName = url.split('/').pop();
      const artifact = mockArtifacts.find(a => a.name === artifactName);
      if (artifact) {
        return Promise.resolve(new Response(artifact.content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
      expect(screen.getByText('architecture.md')).toBeInTheDocument();
      expect(screen.getByText('tests.md')).toBeInTheDocument();
    });
  });

  it('shows artifact content when clicked', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const artifactName = url.split('/').pop();
      const artifact = mockArtifacts.find(a => a.name === artifactName);
      if (artifact) {
        return Promise.resolve(new Response(artifact.content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
    });

    // Click the first spec.md button (in the sidebar)
    const buttons = screen.getAllByRole('button', { name: /spec.md/i });
    fireEvent.click(buttons[0]);

    // Check for content in the pre element using getByText with regex
    expect(screen.getByText(/Specification/i)).toBeInTheDocument();
  });

  it('highlights selected artifact', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const artifactName = url.split('/').pop();
      const artifact = mockArtifacts.find(a => a.name === artifactName);
      if (artifact) {
        return Promise.resolve(new Response(artifact.content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('spec.md')).toBeInTheDocument();
    });

    // Click the first spec.md button (in the sidebar)
    const buttons = screen.getAllByRole('button', { name: /spec.md/i });
    fireEvent.click(buttons[0]);

    // The first button should have the blue background class
    expect(buttons[0]).toHaveClass('bg-blue-100');
  });

  it('shows error state when fetch fails', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('Network error'));

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Error/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no artifacts', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response(null, { status: 404 }))
    );

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/No artifacts available/i)).toBeInTheDocument();
    });
  });

  it('displays artifact type labels', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const artifactName = url.split('/').pop();
      const artifact = mockArtifacts.find(a => a.name === artifactName);
      if (artifact) {
        return Promise.resolve(new Response(artifact.content, {
          status: 200,
          headers: { 'Content-Type': 'text/markdown' },
        }));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });

    render(
      <ArtifactViewer
        itemId="ID-001"
        onClose={mockOnClose}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('spec')).toBeInTheDocument();
      expect(screen.getByText('architecture')).toBeInTheDocument();
      expect(screen.getByText('tests')).toBeInTheDocument();
    });
  });
});