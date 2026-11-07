import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect } from 'vitest';
import { CreateItemModal } from '../CreateItemModal';

describe('CreateItemModal priority select (P3-4)', () => {
  test('uses the same lowercase values as the backend, including critical, and defaults to medium', () => {
    render(<CreateItemModal isOpen onClose={() => {}} onCreate={vi.fn(async () => true)} />);
    const select = screen.getByDisplayValue('Medium') as HTMLSelectElement;
    expect(select.value).toBe('medium');
    expect(Array.from(select.options).map(o => o.value)).toEqual(['high', 'medium', 'low', 'critical']);
  });
});
