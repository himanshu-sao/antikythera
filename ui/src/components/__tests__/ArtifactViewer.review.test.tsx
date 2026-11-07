import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Real useArtifacts hook; only the network is faked. These tests pin the D5 review flow:
// the form posts to /api/item/{id}/review, an approve then requests the forward move,
// a needs-revision never moves, and a gated move is only forced by the explicit control.

vi.mock('../artifacts/Timeline', () => ({ Timeline: () => <div data-testid="timeline" /> }));
vi.mock('../artifacts/Mermaid', () => ({ Mermaid: () => <div /> }));

import { ArtifactViewer } from '../ArtifactViewer';
import { setApiToken } from '../../api/client';

type Call = { url: string; method: string; body: any };

interface Routes {
  stage?: string;
  reviewPost?: { status: number; body?: any };
  movePost?: { status: number; body?: any };
}

function jsonRes(status: number, body: any) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as any);
}

function textRes(body: string) {
  return Promise.resolve({ ok: true, status: 200, text: async () => body, json: async () => ({}) } as any);
}

function installFetch(routes: Routes) {
  const calls: Call[] = [];
  const stage = routes.stage ?? 'REVIEW_SPEC';
  const fetchMock = vi.fn((url: string, init: any = {}) => {
    const method = (init.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: init.body ? JSON.parse(init.body) : undefined });
    if (url.endsWith('/review') && method === 'POST') {
      return jsonRes(routes.reviewPost?.status ?? 200, routes.reviewPost?.body ?? { status: 'success' });
    }
    if (url.includes('/api/move') && method === 'POST') {
      // Gated moves are refused unless the request carries force: true, as the backend does.
      if (init.body && JSON.parse(init.body).force === true) {
        return jsonRes(200, { status: 'success' });
      }
      return jsonRes(routes.movePost?.status ?? 200, routes.movePost?.body ?? { status: 'success' });
    }
    if (/\/api\/item\/[^/]+$/.test(url)) {
      return jsonRes(200, { id: 'ID-007', stage, complexity: 'medium' });
    }
    if (url.endsWith('/artifact/spec.md')) return textRes('# Spec');
    if (url.endsWith('/artifact/review.md')) return textRes('');
    return jsonRes(404, { detail: 'not found' });
  });
  (globalThis as any).fetch = fetchMock;
  return { calls, fetchMock };
}

async function openReviewForm() {
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit Review' })).toBeInTheDocument());
}

describe('ArtifactViewer review form (D5)', () => {
  beforeEach(() => {
    (window.alert as any).mockClear();
    sessionStorage.clear();
  });

  test('Approve posts APPROVED to /api/item/{id}/review, then requests the forward move', async () => {
    const onClose = vi.fn();
    const { calls } = installFetch({ stage: 'REVIEW_SPEC' });
    render(<ArtifactViewer itemId="ID-007" onClose={onClose} />);
    await openReviewForm();

    fireEvent.change(screen.getByLabelText('Comments'), { target: { value: 'looks good' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const review = calls.find((c) => c.url.endsWith('/api/item/ID-007/review'));
    expect(review).toBeDefined();
    expect(review!.method).toBe('POST');
    expect(review!.body).toEqual({ status: 'APPROVED', comment: 'looks good' });

    const move = calls.find((c) => c.url.includes('/api/move'));
    expect(move!.body).toEqual({ item_id: 'ID-007', new_stage: 'ARCHITECTURE' });
    expect(move!.body).not.toHaveProperty('force');
    // The review is recorded before the move.
    expect(calls.indexOf(review!)).toBeLessThan(calls.indexOf(move!));
    expect(window.alert).toHaveBeenCalledWith('Review Approved! Transitioning to ARCHITECTURE');
  });

  test('Needs revision posts NEEDS_REVISION with the comment and never moves the item', async () => {
    const onClose = vi.fn();
    const { calls } = installFetch({ stage: 'REVIEW_SPEC' });
    render(<ArtifactViewer itemId="ID-007" onClose={onClose} />);
    await openReviewForm();

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'NEEDS_REVISION' } });
    fireEvent.change(screen.getByLabelText('Comments'), { target: { value: 'add error cases' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));

    await waitFor(() =>
      expect(window.alert).toHaveBeenCalledWith('Feedback submitted. Task remains in REVIEW_SPEC'),
    );
    const review = calls.find((c) => c.url.endsWith('/api/item/ID-007/review'));
    expect(review!.body).toEqual({ status: 'NEEDS_REVISION', comment: 'add error cases' });
    expect(calls.some((c) => c.url.includes('/api/move'))).toBe(false);
    expect(onClose).not.toHaveBeenCalled();
    // The form no longer writes review.md directly.
    expect(calls.some((c) => c.method === 'POST' && c.url.includes('/artifact/review.md'))).toBe(false);
  });

  test('a failed review POST moves nothing and says so', async () => {
    const { calls } = installFetch({ stage: 'REVIEW_SPEC', reviewPost: { status: 500 } });
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    await openReviewForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));
    await waitFor(() =>
      expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Nothing was moved')),
    );
    expect(calls.some((c) => c.url.includes('/api/move'))).toBe(false);
  });

  test('a gated move (422) is reported and shows a labelled Force move control, not a silent force', async () => {
    const { calls } = installFetch({
      stage: 'REVIEW_SPEC',
      movePost: { status: 422, body: { detail: 'Review gate: item is in REVIEW_SPEC' } },
    });
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    await openReviewForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));

    const force = await screen.findByRole('button', { name: /Force move to ARCHITECTURE/i });
    expect(force).toHaveTextContent(/overrides the review and tier rules/i);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Use "Force move" to override'));
    // Only the non-forced move was sent so far.
    const moves = calls.filter((c) => c.url.includes('/api/move'));
    expect(moves).toHaveLength(1);
    expect(moves[0].body).not.toHaveProperty('force');
  });

  test('Force move sends force: true to /api/move only after the explicit click', async () => {
    const onClose = vi.fn();
    const { calls } = installFetch({
      stage: 'REVIEW_SPEC',
      movePost: { status: 422, body: { detail: 'blocked' } },
    });
    render(<ArtifactViewer itemId="ID-007" onClose={onClose} />);
    await openReviewForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));
    const force = await screen.findByRole('button', { name: /Force move to ARCHITECTURE/i });

    // No force request before the explicit click.
    expect(calls.filter((c) => c.url.includes('/api/move')).some((c) => c.body.force)).toBe(false);

    fireEvent.click(force);
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    const forced = calls.filter((c) => c.url.includes('/api/move')).filter((c) => c.body.force === true);
    expect(forced).toHaveLength(1);
    expect(forced[0].body).toEqual({ item_id: 'ID-007', new_stage: 'ARCHITECTURE', force: true });
  });

  test('a stored API token reaches the review POST as a bearer header (apiFetch end to end)', async () => {
    setApiToken('tok-review');
    const { fetchMock } = installFetch({ stage: 'REVIEW_SPEC' });
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    await openReviewForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));
    await waitFor(() => expect(window.alert).toHaveBeenCalled());
    const reviewCall = fetchMock.mock.calls.find((c: any[]) => String(c[0]).endsWith('/review'));
    expect(new Headers(reviewCall![1].headers).get('Authorization')).toBe('Bearer tok-review');
    sessionStorage.clear();
  });

  test('the forward move is not offered as a force on a successful approve', async () => {
    installFetch({ stage: 'REVIEW_SPEC' });
    render(<ArtifactViewer itemId="ID-007" onClose={() => {}} />);
    await openReviewForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));
    await waitFor(() => expect(window.alert).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /Force move/i })).not.toBeInTheDocument();
  });
});
