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
  test('renders all 7 nav items with correct labels', () => {
    render(<App />);
    const navItems = [
      'Home',
      'Orchestrator',
      'Studio',
      'Workflows',
      'Integrations',
      'AI Engine',
      'Settings',
    ];
    navItems.forEach((label) => {
      const btns = screen.getAllByRole('button', { name: new RegExp('^' + label + '$', 'i') });
      expect(btns.length).toBeGreaterThan(0);
    });
  });

  test('active nav item displays teal pill background', () => {
    render(<App />);
    const active = screen.getByRole('button', { name: /Home/i });
    expect(active.className).toMatch(/bg-\[var\(--accent(-light)?\)\]/);
  });
});
