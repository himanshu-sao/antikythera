import React from 'react';

export const ReviewForm = ({ reviewStatus, setReviewStatus, reviewComments, setReviewComments, submitReview }: any) => (
    <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
      <h3 className="font-bold text-gray-900">Submit Review</h3>
      <div>
        <label htmlFor="review-status" className="block text-sm font-medium text-gray-700">Status</label>
        <select 
          id="review-status"
          className="mt-1 block w-full border border-gray-300 rounded-md p-2"
          value={reviewStatus}
          onChange={(e: any) => setReviewStatus(e.target.value)}
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
          onChange={(e: any) => setReviewComments(e.target.value)}
        />
      </div>
      <button 
        onClick={submitReview}
        className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
      >
        Submit Review
      </button>
    </div>
  );
