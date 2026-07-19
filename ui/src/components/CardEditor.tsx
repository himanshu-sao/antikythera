import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';

interface CardEditorProps {
  itemId: string;
  initialData: {
    title: string;
    description?: string;
    priority: string;
    complexity?: string;
    confidence_score: number;
    source_type?: string;
    source_value?: string;
    due_date?: string;
    history?: Array<{ stage: string; at: string; agent?: string }>;
  };
  onSave: (updates: any) => Promise<void>;
  onDelete?: () => Promise<void>;
  onClose: () => void;
}

export function CardEditor({ itemId, initialData, onSave, onDelete, onClose }: CardEditorProps) {
  const [formData, setFormData] = useState(initialData);
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSave(formData);
      toast.success('Changes saved successfully');
      onClose();
    } catch (e) {
      toast.error('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-gray-900">Edit {itemId}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
          <input
            type="text"
            value={formData.title}
            onChange={e => setFormData({ ...formData, title: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            value={formData.description || ''}
            onChange={e => setFormData({ ...formData, description: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none h-32"
          />
        </div>

        {/* P4.1 — complexity override (matches agents.constants.TIER_STAGES). */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Complexity</label>
          <select
            value={formData.complexity || ''}
            onChange={e => setFormData({ ...formData, complexity: e.target.value || undefined })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
          >
            <option value="">Inherit / auto</option>
            <option value="trivial">Trivial</option>
            <option value="simple">Simple</option>
            <option value="complex">Complex</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <select
              value={formData.priority}
              onChange={e => setFormData({ ...formData, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            >
              <option value="High">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confidence Score (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              value={formData.confidence_score}
              onChange={e => setFormData({ ...formData, confidence_score: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Due Date</label>
            <input
              type="date"
              value={formData.due_date || ''}
              onChange={e => setFormData({ ...formData, due_date: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source Type</label>
            <select
              value={formData.source_type || ''}
              onChange={e => setFormData({ ...formData, source_type: e.target.value, source_value: '' })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
            >
              <option value="">None</option>
              <option value="url">URL</option>
              <option value="directory">Directory</option>
            </select>
          </div>
        </div>
        {formData.source_type && (
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {formData.source_type === 'url' ? 'Source URL' : 'Source Directory'}
              </label>
              <input
                type="text"
                value={formData.source_value || ''}
                onChange={e => setFormData({ ...formData, source_value: e.target.value })}
                placeholder={formData.source_type === 'url' ? 'https://example.com' : '/path/to/directory'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>
        )}

        {/* STAGE HISTORY TIMELINE */}
        {initialData.history && initialData.history.length > 0 && (
          <div className="pt-4 border-t border-gray-100">
            <h4 className="text-sm font-bold text-gray-900 mb-4">Stage History</h4>
            <div className="space-y-4 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
              {initialData.history.map((event, idx) => (
                <div key={idx} className="relative pl-8">
                  <div className="absolute left-0 top-1.5 w-6 h-6 bg-white border-2 border-indigo-500 rounded-full flex items-center justify-center z-10">
                    <div className="w-2 h-2 bg-indigo-500 rounded-full" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs font-bold text-gray-800">{event.stage}</span>
                    <span className="text-[10px] text-gray-500">
                      {new Date(event.at).toLocaleString()} {event.agent ? `by ${event.agent}` : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between pt-4">
          <div>
            {onDelete && (
              <button
                type="button"
                onClick={async () => {
                  if (window.confirm("Are you sure you want to delete this item? This action cannot be undone.")) {
                    setIsSaving(true);
                    try {
                      await onDelete();
                    } finally {
                      setIsSaving(false);
                    }
                  }
                }}
                className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                disabled={isSaving}
              >
                Delete Item
              </button>
            )}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:bg-indigo-400"
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
