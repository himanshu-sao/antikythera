import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AIEngineSettings from '../../ui/src/components/AIEngineSettings';

// Mock config to avoid import.meta issues
jest.mock('../../ui/src/config', () => ({ apiUrl: '' }));

// Mock fetch responses
const mockConfig = {
  default_provider: 'ollama',
  default_model_id: 'llama3.1',
  models: [],
  connection_settings: {
    timeout_seconds: 30,
    max_retries: 3,
    enable_fallback: false,
    enable_caching: false,
  },
};

function mockFetch(url) {
  if (url.endsWith('/api/ai-engine/config')) {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockConfig)
    });
  }
  // default fallback
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
}

globalThis.fetch = jest.fn().mockImplementation(url => mockFetch(url));

describe('AIEngineSettings Add Model flow', () => {
  test('opens add model modal when button clicked', async () => {
    render(<AIEngineSettings />);
    // wait for loading to finish
    await waitFor(() => expect(screen.getByText('AI Engine Configuration')).toBeInTheDocument());

    const addButton = screen.getByRole('button', { name: /Add Model/i });
    fireEvent.click(addButton);

    // modal should appear
    expect(screen.getByText('Add New Model')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Model ID (unique)')).toBeInTheDocument();
  });
});
