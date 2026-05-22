# Playwright E2E Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a robust end-to-end test suite using Playwright to verify the core functionality of the Hermes Pipeline UI.

**Architecture:** 
- Use the Page Object Model (POM) to encapsulate page-specific logic and selectors.
- Implement a set of "Golden Path" tests for critical user flows.
- Include tests for edge cases: empty states, API failures, and invalid inputs.
- Mock the backend API using Playwright's `route` to ensure deterministic tests.

**Tech Stack:** Playwright, TypeScript, Vite (UI), FastAPI (Backend).

---

## File Structure

**New Files:**
- `tests/e2e/page-objects/PipelinePage.ts`: POM for the main Kanban board and modals.
- `tests/e2e/pipeline.spec.ts`: Main test suite containing the test cases.
- `playwright.config.ts`: Playwright configuration.

---

## Implementation Tasks

### Task 1: Playwright Setup

**Files:**
- Create: `playwright.config.ts`

- [ ] **Step 1: Create the configuration file**

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

- [ ] **Step 2: Commit**

```bash
git add playwright.config.ts
git commit -m "test: initialize playwright configuration"
```

### Task 2: Pipeline Page Object Model (POM)

**Files:**
- Create: `tests/e2e/page-objects/PipelinePage.ts`

- [ ] **Step 1: Implement the POM**

```typescript
import { Page, Locator, expect } from '@playwright/test';

export class PipelinePage {
  readonly page: Page;
  readonly newItemButton: Locator;
  readonly searchInput: Locator;
  readonly priorityFilter: Locator;
  readonly stageFilter: Locator;
  readonly workflowButton: Locator;
  readonly createModal: Locator;

  constructor(page: Page) {
    this.page = page;
    this.newItemButton = page.getByRole('button', { name: '+ New Idea' });
    this.searchInput = page.getByPlaceholder('Search ideas...');
    this.priorityFilter = page.locator('select').filter({ hasText: 'All Priorities' });
    this.stageFilter = page.locator('select').filter({ hasText: 'All Stages' });
    this.workflowButton = page.getByRole('button', { name: 'How it works' });
    this.createModal = page.locator('div').filter({ hasText: 'Create New Idea' });
  }

  async goto() {
    await this.page.goto('/');
  }

  async createIdea(id: string, title: string) {
    await this.newItemButton.click();
    await this.page.getByLabel('Item ID').fill(id);
    await this.page.getByLabel('Title').fill(title);
    await this.page.getByRole('button', { name: 'Create Item' }).click();
  }

  async searchIdeas(query: string) {
    await this.searchInput.fill(query);
  }

  async getCardByTitle(title: string) {
    return this.page.locator('div').filter({ hasText: title }).first();
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add tests/e2e/page-objects/PipelinePage.ts
git commit -m "test: add PipelinePage POM"
```

### Task 3: Core Functional Tests (Golden Path)

**Files:**
- Create: `tests/e2e/pipeline.spec.ts`

- [ ] **Step 1: Implement "Create New Idea" test**

```typescript
import { test, expect } from '@playwright/test';
import { PipelinePage } from './page-objects/PipelinePage';

test.describe('Pipeline Core Flows', () => {
  test('should create a new idea and see it in INTAKE', async ({ page }) => {
    const pipeline = new PipelinePage(page);
    await pipeline.goto();
    
    await pipeline.createIdea('TEST-1', 'Verify Playwright Works');
    
    const card = await pipeline.getCardByTitle('Verify Playwright Works');
    await expect(card).toBeVisible();
    await expect(card).toContainText('TEST-1');
  });
});
```

- [ ] **Step 2: Implement "Search and Filtering" test**

```typescript
  test('should filter ideas by search query', async ({ page }) => {
    const pipeline = new PipelinePage(page);
    await pipeline.goto();
    
    await pipeline.searchIdeas('Verify');
    
    const card = await pipeline.getCardByTitle('Verify Playwright Works');
    await expect(card).toBeVisible();
    
    await pipeline.searchIdeas('NonExistentIdea');
    await expect(card).not.toBeVisible();
  });
```

- [ ] **Step 3: Implement "Workflow Guide" test**

```typescript
  test('should open and close workflow guide', async ({ page }) => {
    const pipeline = new PipelinePage(page);
    await pipeline.goto();
    
    await pipeline.workflowButton.click();
    await expect(page.getByText('Workflow Guide')).toBeVisible();
    
    await page.getByRole('button', { name: '✕' }).click();
    await expect(page.getByText('Workflow Guide')).not.toBeVisible();
  });
```

- [ ] **Step 4: Run tests to verify**

Run: `npx playwright test tests/e2e/pipeline.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/pipeline.spec.ts
git commit -m "test: add core golden path e2e tests"
```

### Task 4: Advanced Interactions & Edge Cases

**Files:**
- Modify: `tests/e2e/pipeline.spec.ts`

- [ ] **Step 1: Implement "Drag and Drop" test**

Note: This tests the interaction between `DndContext` and the backend `/api/move` call.

```typescript
  test('should move card between stages', async ({ page }) => {
    const pipeline = new PipelinePage(page);
    await pipeline.goto();
    
    const card = await pipeline.getCardByTitle('Verify Playwright Works');
    const targetColumn = page.locator('div').filter({ hasText: 'REFINEMENT' }).first();
    
    await card.dragTo(targetColumn);
    
    // Verify card is now in the REFINEMENT column
    await expect(targetColumn).toContainText('Verify Playwright Works');
  });
```

- [ ] **Step 2: Implement "API Error Handling" test**

```typescript
  test('should show error message when API fails', async ({ page }) => {
    await page.route('**/api/state', route => route.fulfill({
      status: 500,
      body: JSON.stringify({ detail: 'Internal Server Error' })
    }));
    
    const pipeline = new PipelinePage(page);
    await pipeline.goto();
    
    await expect(page.getByText('Error: Internal Server Error')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });
```

- [ ] **Step 3: Run tests to verify**

Run: `npx playwright test tests/e2e/pipeline.spec.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/pipeline.spec.ts
git commit -m "test: add drag-and-drop and error handling tests"
```
