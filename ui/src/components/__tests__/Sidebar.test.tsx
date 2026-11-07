import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../../App';

// Mock fetch to avoid network calls
global.fetch = () => Promise.resolve({ ok: true, json: async () => ({}) } as any);
// Mock localStorage
global.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
  clear: () => {},
} as any;

describe('Sidebar navigation items', () => {
  test('renders the nav items with correct labels', () => {
    render(<App />);
    const navItems = [
      'Home',
      'Orchestrator',
      'Studio',
      'Workflows',
      'Integrations',
      'AI Engine',
    ];
    navItems.forEach((label) => {
      const btns = screen.getAllByRole('button', { name: new RegExp('^' + label + '$', 'i') });
      expect(btns.length).toBeGreaterThan(0);
    });
  });

  test('U5: the dead Settings nav entry is gone', () => {
    render(<App />);
    expect(screen.queryByRole('button', { name: /^Settings$/i })).not.toBeInTheDocument();
  });

  test('U5: profile footer shows a neutral label, not the hard-coded Acme/Enterprise placeholder', () => {
    render(<App />);
    expect(screen.queryByText(/Acme/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Enterprise/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('Local workspace').length).toBeGreaterThan(0);
  });

  test('U5: no external avatar request (ui-avatars.com) and inline initials avatars instead', () => {
    const { container } = render(<App />);
    expect(container.innerHTML).not.toContain('ui-avatars.com');
    expect(container.querySelector('img[src*="avatars"]')).toBeNull();
    expect(screen.getAllByTestId('initials-avatar').length).toBeGreaterThan(0);
  });

  test('active nav item displays teal pill background', () => {
    render(<App />);
    const active = screen.getByRole('button', { name: /Home/i });
    expect(active.className).toMatch(/bg-\[var\(--accent(-light)?\)\]/);
  });
});
