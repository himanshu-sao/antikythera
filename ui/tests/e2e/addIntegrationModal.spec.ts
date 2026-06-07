import { test, expect } from '@playwright/test';

test.describe('Integrations Add Connection Modal', () => {
  test.beforeEach(async ({ page }) => {
    // Mock integrations API (empty list)
    await page.route('http://localhost:8000/api/integrations*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ integrations: [] }),
      });
    });
    await page.goto('/');
    await page.click('text=Integrations');
    await page.waitForResponse(resp => resp.url().includes('/api/integrations') && resp.status() === 200);
  });

  test('opens Add Integration modal with proper ARIA and focus', async ({ page }) => {
    await page.click('text=+ Add Connection');
    const dialog = page.locator('[role="dialog"][aria-modal="true"][aria-labelledby="add-modal-title"]');
    await expect(dialog).toBeVisible();
    await expect(page.locator('#add-modal-title')).toBeVisible();
    // Verify first input is focused
    await expect(page.locator('input[placeholder="e.g. GitHub Production"]').first()).toBeFocused();
    // Verify form fields exist
    await expect(page.locator('text=Connection Name')).toBeVisible();
    await expect(page.locator('text=Connector Type')).toBeVisible();
    await expect(page.locator('button', { hasText: 'Cancel' })).toBeVisible();
    await expect(page.locator('button', { hasText: 'Add Connection' })).toBeVisible();
  });

  test('focus returns to Add Connection card after closing modal', async ({ page }) => {
    await page.click('text=+ Add Connection');
    await page.click('button', { hasText: 'Cancel' });
    // The Add Connection card should regain focus
    const addCard = page.locator('div[tabindex][text=+ Add Connection]');
    await expect(addCard).toBeFocused();
  });

  test('opens Secret Vault modal with proper ARIA and focus', async ({ page }) => {
    await page.click('text=Manage Secrets');
    const dialog = page.locator('[role="dialog"][aria-modal="true"][aria-labelledby="secret-modal-title"]');
    await expect(dialog).toBeVisible();
    await expect(page.locator('#secret-modal-title')).toBeVisible();
    // Verify first input is focused
    await expect(page.locator('input[placeholder="e.g. github_prod"]').first()).toBeFocused();
    await expect(page.locator('text=Profile ID')).toBeVisible();
    await expect(page.locator('text=Secrets (JSON)')).toBeVisible();
  });
});
