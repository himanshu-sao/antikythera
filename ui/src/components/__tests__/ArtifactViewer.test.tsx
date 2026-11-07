import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../../config', () => ({ apiUrl: 'http://configured.test:9999' }));
vi.mock('../artifacts/Timeline', () => ({ Timeline: () => <div data-testid="timeline" /> }));
vi.mock('../artifacts/Mermaid', () => ({
  Mermaid: ({ chart }: { chart: string }) => <div data-testid="mermaid">{chart}</div>,
}));

const artifact = { name: 'spec md.md', content: '# Title\n\nbody text', type: 'spec' as const };
const hookState: any = {
  artifacts: [artifact],
  loading: false,
  selectedArtifact: artifact,
  setSelectedArtifact: vi.fn(),
  error: null,
  reviewStatus: 'APPROVED',
  setReviewStatus: vi.fn(),
  reviewComments: '',
  setReviewComments: vi.fn(),
  isSaving: false,
  itemDetails: null,
  handleContentChange: vi.fn(),
  submitReview: vi.fn(),
  needsReview: false,
};
vi.mock('../../hooks/useArtifacts', () => ({ useArtifacts: () => hookState }));

import { ArtifactViewer } from '../ArtifactViewer';

describe('ArtifactViewer', () => {
  beforeEach(() => {
    (globalThis as any).fetch = vi.fn(() => Promise.resolve({ ok: true, json: async () => ({}) }));
    (window.confirm as any).mockReturnValue(true);
    (window.alert as any).mockClear();
    hookState.selectedArtifact = artifact;
    hookState.artifacts = [artifact];
  });

  test('promote call uses the configured API base, not a hard-coded localhost', async () => {
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Promote to Pattern/i }));
    await waitFor(() => expect((globalThis as any).fetch).toHaveBeenCalled());
    const [url, init] = (globalThis as any).fetch.mock.calls[0];
    expect(url.startsWith('http://configured.test:9999/api/item/ID-007/promote-pattern')).toBe(true);
    expect(url).not.toContain('localhost:8006');
    // artifact name is URL-encoded
    expect(url).toContain('artifact_name=spec%20md.md');
    expect(init.method).toBe('POST');
  });

  test('does nothing when the user cancels the confirm dialog', () => {
    (window.confirm as any).mockReturnValueOnce(false);
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Promote to Pattern/i }));
    expect((globalThis as any).fetch).not.toHaveBeenCalled();
  });

  test('alerts on a failed promotion', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    (globalThis as any).fetch = vi.fn(() => Promise.resolve({ ok: false, json: async () => ({}) }));
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Promote to Pattern/i }));
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Error promoting pattern.'));
  });

  test('renders markdown through the statically imported react-markdown', () => {
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    expect(screen.getByText('body text')).toBeInTheDocument();
  });

  test('renders a mermaid fenced block through the Mermaid component', () => {
    hookState.selectedArtifact = { name: 'architecture.md', type: 'architecture', content: '```mermaid\ngraph TD; A-->B\n```' };
    hookState.artifacts = [hookState.selectedArtifact];
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    expect(screen.getByTestId('mermaid').textContent).toContain('graph TD; A-->B');
  });
});
