import React from 'react';
import type { GatedMove } from '../../hooks/useArtifacts';

export interface ReviewFormProps {
  reviewStatus: string;
  setReviewStatus: (status: string) => void;
  reviewComments: string;
  setReviewComments: (comments: string) => void;
  submitReview: () => void;
  /** Set when the last approved move was refused by the server (422). */
  gatedMove?: GatedMove | null;
  /** Explicit override for a gated move. Only ever sends force=true. */
  forceMove?: () => void;
}

export const ReviewForm = ({
  reviewStatus,
  setReviewStatus,
  reviewComments,
  setReviewComments,
  submitReview,
  gatedMove,
  forceMove,
}: ReviewFormProps) => (
  <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
    <h3 className="font-bold text-gray-900">Submit Review</h3>
    <div>
      <label htmlFor="review-status" className="block text-sm font-medium text-gray-700">Status</label>
      <select
        id="review-status"
        className="mt-1 block w-full border border-gray-300 rounded-md p-2"
        value={reviewStatus}
        onChange={(e) => setReviewStatus(e.target.value)}
      >
        <option value="APPROVED">Approved</option>
        <option value="NEEDS_REVISION">Needs Revision</option>
      </select>
    </div>
    <div>
      <label htmlFor="review-comments" className="block text-sm font-medium text-gray-700">Comments</label>
      <textarea
        id="review-comments"
        className="mt-1 block w-full border border-gray-300 rounded-md p-2 h-32"
        value={reviewComments}
        onChange={(e) => setReviewComments(e.target.value)}
      />
    </div>
    <button
      type="button"
      onClick={submitReview}
      className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
    >
      Submit Review
    </button>
    {gatedMove && forceMove && (
      <div role="alert" className="border border-amber-300 bg-amber-50 rounded-md p-3 space-y-2">
        <p className="text-sm text-amber-800">
          The move to <span className="font-semibold">{gatedMove.stage}</span> was blocked by the
          move rules: {gatedMove.reason}
        </p>
        <button
          type="button"
          onClick={forceMove}
          className="w-full border border-amber-600 text-amber-800 py-2 rounded-md hover:bg-amber-100"
        >
          Force move to {gatedMove.stage} (overrides the review and tier rules)
        </button>
      </div>
    )}
  </div>
);
