import { test, expect } from '@playwright/test';
import { PipelinePage } from './page-objects/PipelinePage';

test.describe('Pipeline Golden Path', () => {
  let pipelinePage: PipelinePage;

  test.beforeEach(async ({ page }) => {
    pipelinePage = new PipelinePage(page);

    // Mock initial state
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: {
            'IDEA-1': {
              id: 'IDEA-1',
              title: 'Existing Idea',
              stage: 'INTAKE',
              priority: 'medium',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 0,
            },
          },
        }),
      });
    });

    await pipelinePage.goto();
  });

  test('should create a new idea and see it in INTAKE', async ({ page }) => {
    const newId = 'IDEA-NEW';
    const newTitle = 'New Awesome Idea';

    // Mock create item API
    await page.route('**/api/items', async (route) => {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: newId,
          title: newTitle,
          stage: 'INTAKE',
        }),
      });
    });

    // Mock state update after creation
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: {
            'IDEA-1': {
              id: 'IDEA-1',
              title: 'Existing Idea',
              stage: 'INTAKE',
              priority: 'medium',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 0,
            },
            [newId]: {
              id: newId,
              title: newTitle,
              stage: 'INTAKE',
              priority: 'medium',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 1,
            },
          },
        }),
      });
    });

    await pipelinePage.createIdea(newId, newTitle);

    const card = await pipelinePage.getCardByTitle(newTitle);
    await expect(card).toBeVisible();
    await expect(card).toContainText('INTAKE');
  });

  test('should filter ideas by search query', async ({ page }) => {
    // Mock state with multiple items
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: {
            'IDEA-1': {
              id: 'IDEA-1',
              title: 'Apple Idea',
              stage: 'INTAKE',
              priority: 'medium',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 0,
            },
            'IDEA-2': {
              id: 'IDEA-2',
              title: 'Banana Idea',
              stage: 'INTAKE',
              priority: 'medium',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 1,
            },
          },
        }),
      });
    });

    await pipelinePage.goto();

    await pipelinePage.searchIdeas('Apple');

    const appleCard = await pipelinePage.getCardByTitle('Apple Idea');
    const bananaCard = await pipelinePage.getCardByTitle('Banana Idea');

    await expect(appleCard).toBeVisible();
    await expect(bananaCard).not.toBeVisible();
  });

  test('should open and close workflow guide', async ({ page }) => {
    await pipelinePage.workflowButton.click();

    const workflowGuide = page.locator('h2', { hasText: 'Workflow Guide' });
    await expect(workflowGuide).toBeVisible();

    // Use the close button in the Workflow Guide modal
    await page.getByRole('button', { name: '✕' }).first().click();

    await expect(workflowGuide).not.toBeVisible();
  });
});
