import React from 'react';

/** Up to two uppercase initials from a display name; "?" when there is nothing usable. */
export function getInitials(name: string | null | undefined): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Inline avatar drawn with local markup only: no image and no external request. */
export function InitialsAvatar({ name, className = '' }: { name: string; className?: string }) {
  return (
    <div
      aria-hidden="true"
      data-testid="initials-avatar"
      className={`rounded-full bg-[var(--accent-light)] text-[var(--accent)] font-semibold flex items-center justify-center select-none ${className}`}
    >
      {getInitials(name)}
    </div>
  );
}
