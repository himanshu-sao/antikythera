import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, test, expect } from 'vitest';
import { InitialsAvatar, getInitials } from '../InitialsAvatar';

describe('getInitials', () => {
  test.each([
    ['Local workspace', 'LW'],
    ['acme corp', 'AC'],
    ['  Single  ', 'SI'],
    ['a b c', 'AB'],
    ['', '?'],
    ['   ', '?'],
    [null, '?'],
    [undefined, '?'],
  ])('%j -> %s', (name, expected) => {
    expect(getInitials(name as any)).toBe(expected);
  });
});

describe('InitialsAvatar', () => {
  test('renders initials and no image element', () => {
    const { container } = render(<InitialsAvatar name="Local workspace" />);
    expect(screen.getByTestId('initials-avatar')).toHaveTextContent('LW');
    expect(container.querySelector('img')).toBeNull();
  });

  test('is hidden from assistive tech (decorative)', () => {
    render(<InitialsAvatar name="X Y" />);
    expect(screen.getByTestId('initials-avatar')).toHaveAttribute('aria-hidden', 'true');
  });
});
