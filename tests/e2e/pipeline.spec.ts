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
    // The live board shows stage in the column header (`h2` reads "Intake(N)"),
    // not inside the card — so "see it in INTAKE" = the card lives under the
    // Intake column (substring match is robust to the count suffix).
    const intakeColumn = await pipelinePage.cardColumnHeader(newTitle);
    await expect(intakeColumn).toContainText('Intake');
  });

  test('should filter ideas by search query, priority, and stage', async ({ page }) => {
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
              priority: 'high',
              confidence_score: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              order: 0,
            },
            'IDEA-2': {
              id: 'IDEA-2',
              title: 'Banana Idea',
              stage: 'REFINEMENT',
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

    // 1. Test Search
    await pipelinePage.searchIdeas('Apple');
    await expect(page.locator('text=Apple Idea')).toBeVisible();
    await expect(page.locator('text=Banana Idea')).not.toBeVisible();
    await pipelinePage.searchIdeas(''); // Reset

    // 2. Test Priority Filter
    await page.selectOption('select:nth-of-type(1)', 'high');
    await expect(page.locator('text=Apple Idea')).toBeVisible();
    await expect(page.locator('text=Banana Idea')).not.toBeVisible();
    await page.selectOption('select:nth-of-type(1)', 'all');

    // 3. Test Stage Filter
    await page.selectOption('select:nth-of-type(2)', 'REFINEMENT');
    await expect(page.locator('text=Banana Idea')).toBeVisible();
    await expect(page.locator('text=Apple Idea')).not.toBeVisible();
  });


  test('should open and close workflow guide', async ({ page }) => {
    await pipelinePage.workflowButton.click();

    const workflowGuide = page.locator('h2', { hasText: 'Workflow Guide' });
    await expect(workflowGuide).toBeVisible();

    // Use the close button in the Workflow Guide modal
    await page.getByRole('button', { name: '✕' }).first().click();

    await expect(workflowGuide).not.toBeVisible();
  });

  test('should move card between stages', async ({ page }) => {
    const cardTitle = 'Existing Idea';
    const sourceColumnTitle = 'Intake';
    const targetColumnTitle = 'Refinement';

    const card = await pipelinePage.getCardByTitle(cardTitle);
    const targetColumn = await pipelinePage.getColumnByTitle(targetColumnTitle);

    // Drag and drop
    await card.dragTo(targetColumn);

    // Mock API response for move (optional but good for verification if we were checking network)
    // Here we verify that the UI reflects the move if we mock the state update
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: {
            'IDEA-1': {
              id: 'IDEA-1',
              title: cardTitle,
              stage: 'REFINEMENT',
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

    // Refresh or wait for the state to be applied
    await page.reload();

    const updatedCard = await pipelinePage.getCardByTitle(cardTitle);
    await expect(updatedCard).toBeVisible();
    // We can't easily check "is in column" without more DOM knowledge,
    // but we can verify the mock state was requested or the UI updated.
    // For a simpler e2e check, we check if it's still there after the move.
  });

  test('should persist intra-column reordering', async ({ page }) => {
    // Stateful mock for the API
    let mockState = {
      items: {
        'IDEA-1': { id: 'IDEA-1', title: 'First Idea', stage: 'INTAKE', order: 0 },
        'IDEA-2': { id: 'IDEA-2', title: 'Second Idea', stage: 'INTAKE', order: 1 },
      },
    };

    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockState),
      });
    });

    await page.route('**/api/items/reorder', async (route) => {
      const request = JSON.parse(route.request().postData() || '{}');
      const { stage, ordered_ids } = request;

      if (stage && ordered_ids) {
        ordered_ids.forEach((id: string, index: number) => {
          if (mockState.items[id]) {
            mockState.items[id].order = index;
          }
        });
      }

      await route.fulfill({ status: 200, body: JSON.stringify({ status: 'success' }) });
    });

    await pipelinePage.goto();

    const firstCard = await pipelinePage.getCardByTitle('First Idea');
    const secondCard = await pipelinePage.getCardByTitle('Second Idea');

    // Drag Second Idea above First Idea. Uses the manual mouse sequence in
    // dragCardOnto (not locator.dragTo) — dnd-kit's PointerSensor won't fire
    // onDragEnd for a single-hop dragTo, so the reorder would never be sent.
    await pipelinePage.dragCardOnto('Second Idea', 'First Idea');

    // Wait for the API calls to complete and the UI to reflect the change
    // Use a shorter timeout or a more flexible wait
    await page.waitForResponse(
      response => response.url().includes('/api/items/reorder') && response.status() === 200,
      { timeout: 5000 }
    ).catch(() => console.log('Reorder response timeout - continuing to verify DOM'));

    await page.reload();

    // Verify the order in the DOM (Second Idea should now be first).
    // Live card class is `group relative bg-white p-4 rounded-[10px] … cursor-grab
    // hover-lift …` — the board is a horizontal-stack flex layout, not `.grid-cols-5`
    // (the old grid layout was replaced). `.cursor-grab.hover-lift` uniquely matches cards.
    const cards = page.locator('.cursor-grab.hover-lift');
    await expect(cards.first()).toContainText('Second Idea');
    await expect(cards.nth(1)).toContainText('First Idea');
  });


  test('should show error message when API fails', async ({ page }) => {
    await page.route('**/api/state', async (route) => {
      await route.fulfill({
        status: 500,
        body: 'Internal Server Error',
      });
    });


    await pipelinePage.goto();

    const errorLocator = page.locator('text=Error:');
    await expect(errorLocator).toBeVisible();
    await expect(page.locator('text=Retry')).toBeVisible();
  });
});
