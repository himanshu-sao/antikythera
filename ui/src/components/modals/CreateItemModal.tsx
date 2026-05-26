import React from 'react';

export const CreateItemModal = ({ isOpen, onClose, onCreate }: { isOpen: boolean, onClose: () => void, onCreate: (data: any) => Promise<boolean> }) => {
  const [newItem, setNewItem] = React.useState({ 
      id: '',
      title: '',
      goal: '',
      description: '',
      priority: 'medium',
      source_type: 'directory',
      source_value: '',
      due_date: ''
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">Create New Idea</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Item ID <span className="text-red-500">*</span></label>
            <input type="text" className="w-full p-2 border rounded" value={newItem.id} onChange={e => setNewItem({...newItem, id: e.target.value})} placeholder="e.g. IDEA-1" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Title <span className="text-red-500">*</span></label>
            <input type="text" className="w-full p-2 border rounded" value={newItem.title} onChange={e => setNewItem({...newItem, title: e.target.value})} />
          </div>
          
          <div className="p-3 bg-indigo-50 rounded-lg border border-indigo-100">
            <label className="block text-sm font-bold text-indigo-900 mb-1">Core Goal (The "What") <span className="text-red-500">*</span></label>
            <p className="text-[10px] text-indigo-700 mb-2">What should the agent actually do?</p>
            <textarea 
              className="w-full p-2 border border-indigo-200 rounded h-20 text-sm" 
              value={newItem.goal} 
              onChange={e => setNewItem({...newItem, goal: e.target.value})} 
              placeholder="e.g. Summarize all errors in the logs..." 
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Additional Description</label>
            <textarea 
              className="w-full p-2 border rounded h-16 text-sm" 
              value={newItem.description} 
              onChange={e => setNewItem({...newItem, description: e.target.value})} 
              placeholder="Any extra notes or context..." 
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Priority</label>
              <select className="w-full p-2 border rounded text-sm" value={newItem.priority} onChange={e => setNewItem({...newItem, priority: e.target.value})}>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Source Type</label>
              <select className="w-full p-2 border rounded text-sm" value={newItem.source_type} onChange={e => setNewItem({...newItem, source_type: e.target.value})}>
                <option value="directory">Directory</option>
                <option value="url">URL</option>
                <option value="text">Direct Text</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Source Context (The "Where")</label>
            <p className="text-[10px] text-gray-500 mb-1">Path, URL, or text snippet</p>
            <input type="text" className="w-full p-2 border rounded text-sm" value={newItem.source_value} onChange={e => setNewItem({...newItem, source_value: e.target.value})} placeholder="e.g. /var/log or https://..." />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Due Date</label>
            <input type="date" className="w-full p-2 border rounded text-sm" value={newItem.due_date} onChange={e => setNewItem({...newItem, due_date: e.target.value})} />
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">Cancel</button>
            <button 
              onClick={async () => {
                if (newItem.id && newItem.title && newItem.goal) {
                  const success = await onCreate(newItem);
                  if (success) onClose();
                } else {
                  alert("Please fill in all required fields (ID, Title, and Goal).");
                }
              }} 
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium shadow-sm"
            >
              Create
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
