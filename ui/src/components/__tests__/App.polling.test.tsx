import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../../App';

// Mock fetch globally for the App component
const fetchMock = jest.fn(() =>
  Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as any)
);

global.fetch = fetchMock as any;

describe('App polling behavior', () => {
  test('fetch is called at least once on render', async () => {
    render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
