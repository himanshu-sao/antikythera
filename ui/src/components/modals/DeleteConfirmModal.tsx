import React from 'react';

export const DeleteConfirmModal = ({ isOpen, onClose, onConfirm, targetId }: { isOpen: boolean, onClose: () => void, onConfirm: () => void, targetId: string | null }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-[60]">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6">
        <h2 className="text-xl font-bold text-red-600 mb-2">Delete Item?</h2>
        <p className="text-gray-600 mb-6">Are you sure you want to delete <span className="font-bold">{targetId}</span>? This cannot be undone.</p>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
          <button onClick={onConfirm} className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">Delete</button>
        </div>
      </div>
    </div>
  );
};
