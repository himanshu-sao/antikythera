import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect } from 'vitest';
import { CardEditor, normalizePriority, PRIORITY_OPTIONS } from '../CardEditor';

const base = {
  title: 'Card',
  description: '',
  complexity: 'auto',
  confidence_score: 50,
  source_type: 'directory',
  source_value: '',
  due_date: '',
};

function renderEditor(priority: string, onSave = vi.fn(() => Promise.resolve())) {
  render(
    <CardEditor
      itemId="ID-1"
      initialData={{ ...base, priority }}
      onSave={onSave}
      onClose={() => {}}
    />,
  );
  return { onSave, select: screen.getByLabelText('Priority') as HTMLSelectElement };
}

describe('CardEditor priority select (P3-4)', () => {
  test('offers lowercase values low, medium, high, critical with capitalised labels', () => {
    const { select } = renderEditor('medium');
    const values = Array.from(select.options).map(o => o.value);
    expect(values).toEqual(['low', 'medium', 'high', 'critical']);
    expect(Array.from(select.options).map(o => o.textContent)).toEqual(['Low', 'Medium', 'High', 'Critical']);
  });

  test('no option has a capitalised value', () => {
    const { select } = renderEditor('medium');
    expect(Array.from(select.options).some(o => /[A-Z]/.test(o.value))).toBe(false);
  });

  test('preselects "high" when the stored value is "high"', () => {
    const { select } = renderEditor('high');
    expect(select.value).toBe('high');
  });

  test('preselects "critical" (previously had no option)', () => {
    const { select } = renderEditor('critical');
    expect(select.value).toBe('critical');
  });

  test('normalises a capitalised incoming value for display and submits lowercase', async () => {
    const { select, onSave } = renderEditor('High');
    expect(select.value).toBe('high');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].priority).toBe('high');
  });

  test('an unknown stored value stays visible rather than silently changing', () => {
    const { select } = renderEditor('urgent');
    expect(select.value).toBe('urgent');
    expect(Array.from(select.options).map(o => o.value)).toContain('urgent');
  });

  test('saving a changed priority sends the lowercase value', async () => {
    const { select, onSave } = renderEditor('low');
    fireEvent.change(select, { target: { value: 'critical' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].priority).toBe('critical');
  });
});

describe('normalizePriority', () => {
  test('lowercases and trims', () => {
    expect(normalizePriority('  High ')).toBe('high');
    expect(normalizePriority('CRITICAL')).toBe('critical');
  });
  test('empty, null or undefined fall back to medium', () => {
    expect(normalizePriority('')).toBe('medium');
    expect(normalizePriority(null)).toBe('medium');
    expect(normalizePriority(undefined)).toBe('medium');
    expect(normalizePriority('   ')).toBe('medium');
  });
  test('PRIORITY_OPTIONS matches the backend VALID_PRIORITIES set', () => {
    expect(PRIORITY_OPTIONS.map(o => o.value)).toEqual(['low', 'medium', 'high', 'critical']);
  });
});
