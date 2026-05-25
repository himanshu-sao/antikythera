import React from 'react';

export const CreateItemModal = ({ isOpen, onClose, onCreate }: { isOpen: boolean, onClose: () => void, onCreate: (data: any) => Promise<boolean> }) => {
  const [newItem, setNewItem] = React.useState({ 
      id: '', 
      title: '', 
      description: '',
      priority: 'medium',
      source_type: 'directory', 
      source_value: '', 
      due_date: '' 
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
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
          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <textarea 
              className="w-full p-2 border rounded h-24" 
              value={newItem.description} 
              onChange={e => setNewItem({...newItem, description: e.target.value})} 
              placeholder="What needs to be done?"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Priority</label>
            <select className="w-full p-2 border rounded" value={newItem.priority} onChange={e => setNewItem({...newItem, priority: e.target.value})}>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Source Type</label>
            <select className="w-full p-2 border rounded" value={newItem.source_type} onChange={e => setNewItem({...newItem, source_type: e.target.value})}>
              <option value="directory">Directory (Local File)</option>
              <option value="url">URL (Web Link)</option>
              <option value="text">Direct Text</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Source Value (Path/URL/Text)</label>
            <input type="text" className="w-full p-2 border rounded" value={newItem.source_value} onChange={e => setNewItem({...newItem, source_value: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Due Date</label>
            <input type="date" className="w-full p-2 border rounded" value={newItem.due_date} onChange={e => setNewItem({...newItem, due_date: e.target.value})} />
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <button onClick={onClose} className="px-4 py-2 text-gray-600">Cancel</button>
            <button onClick={async () => {
              if (newItem.id && newItem.title) {
                const success = await onCreate(newItem);
                if (success) onClose();
              }
            }} className="px-4 py-2 bg-indigo-600 text-white rounded-lg">Create</button>
          </div>
        </div>
      </div>
    </div>
  );
};
