import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { IntegrationsManager } from '../IntegrationsManager';

describe('IntegrationsManager component', () => {
  test('renders header and filter inputs', () => {
    render(<IntegrationsManager />);
    expect(screen.getByRole('heading', { name: /Integrations Hub/i })).toBeInTheDocument();
    // Search input
    const searchInput = screen.getByLabelText(/Search integrations/i);
    expect(searchInput).toBeInTheDocument();
    // Type filter
    const typeSelect = screen.getByLabelText(/Filter by type/i);
    expect(typeSelect).toBeInTheDocument();
    // Status filter
    const statusSelect = screen.getByLabelText(/Filter by status/i);
    expect(statusSelect).toBeInTheDocument();
    // Add Connection button
    expect(screen.getByRole('button', { name: /\+ Add Connection/i })).toBeInTheDocument();
  });
});
