import React, { useState } from 'react';

interface CreateItemModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (data: any) => Promise<boolean>;
}

export const CreateItemModal = ({ isOpen, onClose, onCreate }: CreateItemModalProps) => {
  const [newItem, setNewItem] = useState({ 
      id: '',
      title: '',
      goal: '',
      description: '',
      priority: 'medium',
      source_type: 'directory',
      source_value: '',
      due_date: ''
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  if (!isOpen) return null;

  const validateField = (name: string, value: any) => {
    let error = '';
    switch (name) {
      case 'id':
        if (!value) error = 'ID is required';
        else if (value.length > 50) error = 'Max 50 characters';
        else if (!/^[A-Za-z0-9_-]+$/.test(value)) error = 'Use only letters, numbers, _ or - (no spaces)';
        break;
      case 'title':
        if (!value) error = 'Title is required';
        else if (value.length > 200) error = 'Max 200 characters';
        break;
      case 'goal':
        if (!value) error = 'Goal is required';
        else if (value.length > 2000) error = 'Max 2000 characters';
        break;
      case 'due_date':
        if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) error = 'Format must be YYYY-MM-DD';
        break;
      case 'source_type':
        if (!['url', 'directory', 'text'].includes(value)) error = 'Invalid source type';
        break;
    }

    setErrors(prev => ({ ...prev, [name]: error }));
    return error;
  };

  const handleBlur = (name: string, value: any) => {
    validateField(name, value);
  };

  const handleChange = (name: string, value: any) => {
    setNewItem(prev => ({ ...prev, [name]: value }));
    // Clear error when user starts typing again
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const isFormValid = () => {
    const newErrors: Record<string, string> = {};
    if (!newItem.id) newErrors.id = 'ID is required';
    else if (!/^[A-Za-z0-9_-]+$/.test(newItem.id)) newErrors.id = 'Invalid ID format';
    
    if (!newItem.title) newErrors.title = 'Title is required';
    if (!newItem.goal) newErrors.goal = 'Goal is required';
    
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    // Final validation check before submitting
    const idErr = validateField('id', newItem.id);
    const titleErr = validateField('title', newItem.title);
    const goalErr = validateField('goal', newItem.goal);

    if (!idErr && !titleErr && !goalErr) {
      const success = await onCreate(newItem);
      if (success) onClose();
    } else {
      // If there were errors, they are already set in state by validateField
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">Create New Idea</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Item ID <span className="text-red-500">*</span></label>
            <input 
              type="text" 
              className={`w-full p-2 border rounded ${errors.id ? 'border-red-500' : ''}`} 
              value={newItem.id} 
              onChange={e => handleChange('id', e.target.value)} 
              onBlur={() => handleBlur('id', newItem.id)}
              placeholder="e.g. IDEA-1" 
            />
            {errors.id && <p className="text-red-500 text-xs mt-1">{errors.id}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Title <span className="text-red-500">*</span></label>
            <input 
              type="text" 
              className={`w-full p-2 border rounded ${errors.title ? 'border-red-500' : ''}`} 
              value={newItem.title} 
              onChange={e => handleChange('title', e.target.value)}
              onBlur={() => handleBlur('title', newItem.title)}
            />
            {errors.title && <p className="text-red-500 text-xs mt-1">{errors.title}</p>}
          </div>
          
          <div className="p-3 bg-indigo-50 rounded-lg border border-indigo-100">
            <label className="block text-sm font-bold text-indigo-900 mb-1">Core Goal (The "What") <span className="text-red-500">*</span></label>
            <p className="text-[10px] text-indigo-700 mb-2">What should the agent actually do?</p>
            <textarea 
              className={`w-full p-2 border rounded h-20 text-sm ${errors.goal ? 'border-red-500' : ''}`} 
              value={newItem.goal} 
              onChange={e => handleChange('goal', e.target.value)}
              onBlur={() => handleBlur('goal', newItem.goal)}
              placeholder="e.g. Summarize all errors in the logs..." 
            />
            {errors.goal && <p className="text-red-500 text-xs mt-1">{errors.goal}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Additional Description</label>
            <textarea 
              className="w-full p-2 border rounded h-16 text-sm" 
              value={newItem.description} 
              onChange={e => handleChange('description', e.target.value)} 
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Priority</label>
              <select 
                className="w-full p-2 border rounded text-sm" 
                value={newItem.priority} 
                onChange={e => handleChange('priority', e.target.value)}
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Source Type</label>
              <select 
                className="w-full p-2 border rounded text-sm" 
                value={newItem.source_type} 
                onChange={e => handleChange('source_type', e.target.value)}
                onBlur={() => handleBlur('source_type', newItem.source_type)}
              >
                <option value="directory">Directory</option>
                <option value="url">URL</option>
                <option value="text">Direct Text</option>
              </select>
              {errors.source_type && <p className="text-red-500 text-xs mt-1">{errors.source_type}</p>}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Source Context (The "Where")</label>
            <p className="text-[10px] text-gray-500 mb-1">Path, URL, or text snippet</p>
            <input 
              type="text" 
              className="w-full p-2 border rounded text-sm" 
              value={newItem.source_value} 
              onChange={e => handleChange('source_value', e.target.value)} 
              placeholder="e.g. /var/log or https://..." 
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Due Date</label>
            <input 
              type="date" 
              className={`w-full p-2 border rounded text-sm ${errors.due_date ? 'border-red-500' : ''}`} 
              value={newItem.due_date} 
              onChange={e => handleChange('due_date', e.target.value)}
              onBlur={() => handleBlur('due_date', newItem.due_date)}
            />
            {errors.due_date && <p className="text-red-500 text-xs mt-1">{errors.due_date}</p>}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">Cancel</button>
            <button 
              onClick={handleSubmit}
              className={`px-4 py-2 text-white rounded-lg transition-colors font-medium shadow-sm ${isFormValid() ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-gray-400 cursor-not-allowed'}`}
            >
              Create
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
