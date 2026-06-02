import { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { apiUrl } from '../config';

// Custom hook for managing pipeline state
export function useModalManager() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showWorkflow, setShowWorkflow] = useState(false);
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [showBuilder, setShowBuilder] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // Function to initialize all modals
  const initializeModals = () => {
    setShowCreateModal(false);
    setShowWorkflow(false);
    setShowIntegrations(false);
    setShowBuilder(false);
    setShowDeleteConfirm(false);
    setDeleteTargetId(null);
  };

  // Function to handle modal actions
  const openCreateModal = () => {
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
  };

  const openDeleteConfirm = (itemId: string) => {
    setDeleteTargetId(itemId);
    setShowDeleteConfirm(true);
  };

  const closeDeleteConfirm = () => {
    setDeleteTargetId(null);
    setShowDeleteConfirm(false);
  };

  return {
    // Modal states
    showCreateModal,
    showWorkflow,
    showIntegrations,
    showBuilder,
    showDeleteConfirm,
    
    // Modal control functions
    openCreateModal,
    closeCreateModal,
    openDeleteConfirm,
    closeDeleteConfirm,
    
    // Modal actions
    setShowCreateModal,
    setShowWorkflow,
    setShowIntegrations,
    setShowBuilder,
    setShowDeleteConfirm,
    setDeleteTargetId,
  };
}