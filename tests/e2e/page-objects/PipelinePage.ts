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
    await this.page.locator('input[placeholder="e.g. IDEA-1"]').fill(id);
    await this.page.locator('input[placeholder="What is the automation idea?"]').fill(title);
    await this.page.getByRole('button', { name: 'Create Item' }).click();
  }

  async searchIdeas(query: string) {
    await this.searchInput.fill(query);
  }

  async getCardByTitle(title: string) {
    return this.page.locator('div').filter({ hasText: title }).first();
  }

  async getColumnByTitle(title: string) {
    return this.page.locator('h2', { hasText: title }).first();
  }
}
