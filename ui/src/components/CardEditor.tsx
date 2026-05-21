import React, { useState, useEffect } from 'react';

interface CardEditorProps {
  itemId: string;
  initialData: {
    title: string;
    description?: string;
    priority: string;
    confidence_score: number;
    source_type?: string;
    source_value?: string;
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
      onClose();
    } catch (e) {
      alert('Failed to save changes');
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
          {formData.source_type && (
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
          )}
        </div>

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
