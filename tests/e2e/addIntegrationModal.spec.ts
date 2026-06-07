import { test, expect } from '@playwright/test';

test.describe('Integrations Add Connection Modal', () => {
  test.beforeEach(async ({ page }) => {
    // Mock integrations API to return empty list
    await page.route('**/api/integrations*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ integrations: [] }),
      });
    });
    await page.goto('/');
    await page.click('text=Integrations');
    // Ensure the page has loaded
    await expect(page.locator('text=Integrations Hub')).toBeVisible();
  });

  test('opens Add Integration modal', async ({ page }) => {
    await page.click('text=+ Add Connection');
    await expect(page.locator('text=Add Integration')).toBeVisible();
    await expect(page.locator('text=Connection Name')).toBeVisible();
    await expect(page.locator('text=Connector Type')).toBeVisible();
    await expect(page.locator('button', { hasText: 'Cancel' })).toBeVisible();
    const modal = page.locator('text=Add Integration').locator('..');
    await expect(modal.locator('button', { hasText: 'Add Connection' })).toBeVisible();
  });
});
