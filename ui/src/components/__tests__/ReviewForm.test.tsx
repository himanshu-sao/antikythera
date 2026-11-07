import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect } from 'vitest';
import { ReviewForm } from '../artifacts/ReviewForm';

const base = {
  reviewStatus: 'APPROVED',
  setReviewStatus: vi.fn(),
  reviewComments: '',
  setReviewComments: vi.fn(),
  submitReview: vi.fn(),
};

describe('ReviewForm', () => {
  test('no Force move control without a gated move', () => {
    render(<ReviewForm {...base} forceMove={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Force move/i })).not.toBeInTheDocument();
  });

  test('no Force move control when a gated move exists but no handler is wired', () => {
    render(<ReviewForm {...base} gatedMove={{ stage: 'TESTING', reason: 'r' }} />);
    expect(screen.queryByRole('button', { name: /Force move/i })).not.toBeInTheDocument();
  });

  test('shows the blocked reason and a labelled Force move button naming the stage', () => {
    const forceMove = vi.fn();
    render(
      <ReviewForm {...base} gatedMove={{ stage: 'TESTING', reason: 'Tier path: stage TESTING is skipped' }} forceMove={forceMove} />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Tier path: stage TESTING is skipped');
    const btn = screen.getByRole('button', { name: /Force move to TESTING/i });
    fireEvent.click(btn);
    expect(forceMove).toHaveBeenCalledTimes(1);
    expect(base.submitReview).not.toHaveBeenCalled();
  });

  test('Submit Review button calls submitReview and is a button (not a form submit)', () => {
    const submitReview = vi.fn();
    render(<ReviewForm {...base} submitReview={submitReview} />);
    fireEvent.click(screen.getByRole('button', { name: 'Submit Review' }));
    expect(submitReview).toHaveBeenCalledTimes(1);
  });
});
