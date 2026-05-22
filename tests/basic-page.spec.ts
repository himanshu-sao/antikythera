import { test, expect } from '@playwright/test';

// Define the target URL for our local development server
const TARGET_URL = 'http://localhost:5173/';

test('Website should load successfully on localhost', async ({ page }) => {
  // Navigate to the specified URL
  await page.goto(TARGET_URL);

  // Assert that the page content is loaded and visible.
  // We'll wait for the body element, which is a basic sign of successful DOM rendering.
  const body = page.locator('body');
  await expect(body).toBeVisible();
});
