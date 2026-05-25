import React, { useState } from 'react';
import { apiUrl } from '../config';
import toast from 'react-hot-toast';

interface Comment {
  id: string;
  author: string;
  body: string;
  createdAt: string;
}

interface CommentSectionProps {
  itemId: string;
  initialComments: Comment[];
  onCommentAdded: () => void;
}

export function CommentSection({ itemId, initialComments, onCommentAdded }: CommentSectionProps) {
  const [commentText, setCommentText] = useState('');
  const [isPosting, setIsPosting] = useState(false);

  const handleDeleteComment = async (commentId: string) => {
    if (!window.confirm("Delete this comment?")) return;
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}/comment/${commentId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete comment');
      await onCommentAdded();
      toast.success('Comment deleted');
    } catch (e: any) {
      toast.error(e.message || 'Error deleting comment');
    }
  };

  const getUserIdentity = (): string => {
    const storedName = localStorage.getItem('antikythera_user_name');
    if (storedName) return storedName;

    const name = window.prompt('Please enter your name for comments:', 'Anonymous User');
    const finalName = name?.trim() || 'Anonymous User';
    localStorage.setItem('antikythera_user_name', finalName);
    return finalName;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    setIsPosting(true);
    try {
      const res = await fetch(`${apiUrl}/api/item/${itemId}/comment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          author: getUserIdentity(),
          body: commentText,
        }),
      });

      if (!res.ok) throw new Error('Failed to post comment');

      setCommentText('');
      await onCommentAdded();
    } catch (e) {
      toast.error('Error posting comment');
    } finally {
      setIsPosting(false);
    }
  };

  return (
    <div className="mt-8 border-t border-gray-100 pt-6">
      <h4 className="text-sm font-bold text-gray-900 mb-4">Comments</h4>
      
      <div className="space-y-4 mb-6">
        {initialComments.length === 0 ? (
          <p className="text-xs text-gray-400 italic">No comments yet. Be the first to add one!</p>
        ) : (
          initialComments.map(comment => (
            <div key={comment.id} className="bg-gray-50 p-3 rounded-lg border border-gray-100 group">
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-bold text-gray-700">{comment.author}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400">{new Date(comment.createdAt).toLocaleString()}</span>
                  <button 
                    onClick={() => handleDeleteComment(comment.id)}
                    className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all text-[10px]"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-600">{comment.body}</p>
            </div>
          ))
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={commentText}
          onChange={e => setCommentText(e.target.value)}
          placeholder="Add a comment..."
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
        />
        <button
          type="submit"
          disabled={isPosting || !commentText.trim()}
          className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:bg-indigo-400"
        >
          {isPosting ? '...' : 'Post'}
        </button>
      </form>
    </div>
  );
}
