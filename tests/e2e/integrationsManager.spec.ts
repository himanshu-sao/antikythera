import { test, expect } from '@playwright/test';

test.describe('Integrations Manager UI', () => {
  const mockIntegrations = [
    {
      name: 'GitHub Prod',
      type: 'native',
      status: 'connected',
      description: 'GitHub integration',
    },
    {
      name: 'Jira Dev',
      type: 'mcp',
      status: 'error',
      description: 'Jira integration',
    },
  ];

  test.beforeEach(async ({ page }) => {
    // Mock the integrations API endpoint
    await page.route('http://localhost:8000/api/integrations*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ integrations: mockIntegrations }),
      });
    });
    await page.goto('/');
    // Navigate to Integrations via the top navigation
    await page.click('text=Integrations');
    // Wait for the integrations API response
    await page.waitForResponse(resp => resp.url().includes('/api/integrations') && resp.status() === 200);
  });

  test('renders integration cards and Add Connection CTA', async ({ page }) => {
    // Verify integration cards are displayed
    await expect(page.locator('text=GitHub Prod')).toBeVisible();
    await expect(page.locator('text=Jira Dev')).toBeVisible();
    // Verify status badges
    await expect(page.locator('text=Connected')).toBeVisible();
    await expect(page.locator('text=Error')).toBeVisible();
    // Verify Add Connection CTA card exists
    await expect(page.locator('text=+ Add Connection')).toBeVisible();
  });

  test('type filter works', async ({ page }) => {
    // Open type filter combobox and select 'Native'
    await page.click('text=All Types');
    await page.click('text=Native');
    // Only native integration should be visible
    await expect(page.locator('text=GitHub Prod')).toBeVisible();
    await expect(page.locator('text=Jira Dev')).toBeHidden();
  });
});
