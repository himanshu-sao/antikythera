import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import AIEngineSettings from '../AIEngineSettings';

// Mock fetch to return empty config for simplicity
global.fetch = global.fetch || jest.fn(() => Promise.resolve({ ok: true, json: async () => ({}) } as any));

describe('AIEngineSettings component', () => {
  test('renders loading state initially', () => {
    render(<AIEngineSettings />);
    // Loading spinner text should be present
    expect(screen.getByText(/Loading AI Engine configuration.../i)).toBeInTheDocument();
  });
});
