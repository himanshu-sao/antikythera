import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { TokenGate } from '../TokenGate';
import { AUTH_REQUIRED_EVENT, TOKEN_STORAGE_KEY, setApiToken } from '../../api/client';

const fireAuthRequired = () =>
  act(() => {
    window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
  });

describe('TokenGate', () => {
  beforeEach(() => sessionStorage.clear());

  test('is hidden until the auth-required event fires', () => {
    render(<TokenGate onSaved={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireAuthRequired();
    expect(screen.getByRole('dialog', { name: /API token required/i })).toBeInTheDocument();
  });

  test('Save stores the trimmed token and calls onSaved (retry)', () => {
    const onSaved = vi.fn();
    render(<TokenGate onSaved={onSaved} />);
    fireAuthRequired();
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: '  secret-tok  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBe('secret-tok');
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('Save reloads the page when no onSaved is given', () => {
    const reload = vi.fn();
    const original = window.location;
    Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload } });
    try {
      render(<TokenGate />);
      fireAuthRequired();
      fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'tok' } });
      fireEvent.click(screen.getByRole('button', { name: 'Save' }));
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: original });
    }
  });

  test('a blank token shows an error and stores nothing', () => {
    const onSaved = vi.fn();
    render(<TokenGate onSaved={onSaved} />);
    fireAuthRequired();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Paste the API token/);
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(onSaved).not.toHaveBeenCalled();
  });

  test('the input is a password field so the token is not shown', () => {
    render(<TokenGate onSaved={vi.fn()} />);
    fireAuthRequired();
    expect(screen.getByLabelText('Token')).toHaveAttribute('type', 'password');
  });

  test('Dismiss closes without storing, and the next event reopens it', () => {
    render(<TokenGate onSaved={vi.fn()} />);
    fireAuthRequired();
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'typed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    fireAuthRequired();
    expect(screen.getByLabelText('Token')).toHaveValue('');
  });

  test('Clear saved token removes the stored token', () => {
    setApiToken('old-tok');
    render(<TokenGate onSaved={vi.fn()} />);
    fireAuthRequired();
    fireEvent.click(screen.getByRole('button', { name: /Clear saved token/i }));
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('removes its event listener on unmount', () => {
    const { unmount } = render(<TokenGate onSaved={vi.fn()} />);
    unmount();
    fireAuthRequired();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
