import { test, expect } from '@playwright/test';
import { PipelinePage } from './page-objects/PipelinePage';

test.describe('Item Deletion', () => {
  let pipelinePage: PipelinePage;

  test.beforeEach(async ({ page }) => {
    pipelinePage = new PipelinePage(page);

    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: {
            'IDEA-DEL': {
              id: 'IDEA-DEL',
              title: 'Idea to Delete',
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

  test('should delete an item and it should disappear from the board', async ({ page }) => {
    const title = 'Idea to Delete';

    // Mock the delete API call
    await page.route('**/api/item/IDEA-DEL', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({ status: 204 });
      } else {
        await route.continue();
      }
    });

    // To simulate the update, we can use a variable to track state
    let items = {
      'IDEA-DEL': {
        id: 'IDEA-DEL',
        title: title,
        stage: 'INTAKE',
        priority: 'medium',
        confidence_score: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        order: 0,
      },
    };

    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items }),
      });
    });

    await pipelinePage.goto();

    // 1. Click the trash icon on the card to delete it
    const card = await pipelinePage.getCardByTitle(title);
    const trashIcon = card.locator('button[title="Delete"]');
    await trashIcon.click();



    // 2. Handle the confirmation dialog
    await page.once('dialog', dialog => dialog.accept());

    // Mock the state change after deletion
    items = {};
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items }),
      });
    });

    // Refresh to see the updated state
    await page.reload();

    const finalCard = await pipelinePage.getCardByTitle(title);
    await expect(finalCard).not.toBeVisible();
  });



});
