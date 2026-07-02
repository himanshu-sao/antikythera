import { test, expect } from '@playwright/test';

test.describe('Integrations Manager UI', () => {
  const mockIntegrations = [
    {
      name: 'bob-pr-reviewer',
      type: 'mcp',
      status: 'connected',
      description: 'MCP integration for PR review',
    },
    {
      name: 'jira_test',
      type: 'native',
      status: 'connected',
      description: 'Jira native integration',
    },
  ];

  test.beforeEach(async ({ page }) => {
    // Mock the integrations API endpoint to return array directly (matches actual API)
    await page.route('**/api/integrations*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockIntegrations),
      });
    });
    await page.goto('/');
    // Navigate to Integrations via the top navigation - click the Integrations tab
    await page.click('button:has-text("Integrations")');
    // Wait a bit for the UI to render
    await page.waitForTimeout(1000);
  });

  test('renders integration cards and Add Connection CTA', async ({ page }) => {
    // Verify integration cards are displayed
    await expect(page.locator('text=bob-pr-reviewer')).toBeVisible();
    await expect(page.locator('text=jira_test')).toBeVisible();
    // Verify status badges - use more specific locator for the badge
    await expect(page.locator('.bg-green-100.text-green-700:has-text("Connected")').first()).toBeVisible({ timeout: 10000 });
    // Verify Add Connection CTA button exists (not the span)
    await expect(page.locator('button:has-text("+ Add Connection")')).toBeVisible();
  });

  test('type filter works', async ({ page }) => {
    // Open type filter combobox and select 'MCP'
    await page.selectOption('select[aria-label="Filter by type"]', 'mcp');
    // Only mcp integration should be visible
    await expect(page.locator('text=bob-pr-reviewer')).toBeVisible();
    await expect(page.locator('text=jira_test')).toBeHidden();
  });
});
