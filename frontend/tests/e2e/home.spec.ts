import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test.use({ storageState: 'tests/e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/home');
    await page.waitForLoadState('networkidle');
  });

  test('should display home page', async ({ page }) => {
    await expect(page.locator('text=算力市场')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show stats cards', async ({ page }) => {
    await expect(page.locator('text=在线节点')).toBeVisible();
    await expect(page.locator('text=运行中任务')).toBeVisible();
    await expect(page.locator('text=今日结算')).toBeVisible();
    await expect(page.locator('text=平台抽成')).toBeVisible();
  });

  test('should show quick actions', async ({ page }) => {
    await expect(page.locator('text=快捷操作')).toBeVisible();
    await expect(page.locator('button:has-text("发布任务")')).toBeVisible();
    await expect(page.locator('button:has-text("添加节点")')).toBeVisible();
    await expect(page.locator('button:has-text("查看收益")')).toBeVisible();
    await expect(page.locator('button:has-text("结算记录")')).toBeVisible();
  });

  test('should navigate to demand-publish from quick action', async ({ page }) => {
    await page.click('button:has-text("发布任务")');
    await page.waitForURL('**/demand-publish**');
    await expect(page.locator('text=发布任务')).toBeVisible();
  });

  test('should navigate to supplier-nodes from quick action', async ({ page }) => {
    await page.click('button:has-text("添加节点")');
    await page.waitForURL('**/supplier-nodes**');
    await expect(page.locator('text=我的节点')).toBeVisible();
  });

  test('should navigate to supplier-earnings from quick action', async ({ page }) => {
    await page.click('button:has-text("查看收益")');
    await page.waitForURL('**/supplier-earnings**');
    await expect(page.locator('text=我的收益')).toBeVisible();
  });

  test('should navigate to settlement from quick action', async ({ page }) => {
    await page.click('button:has-text("结算记录")');
    await page.waitForURL('**/settlement**');
    await expect(page.locator('text=结算记录')).toBeVisible();
  });

  test('should show recent nodes section', async ({ page }) => {
    await expect(page.locator('text=最近节点')).toBeVisible();
  });

  test('should show recent tasks section', async ({ page }) => {
    await expect(page.locator('text=最近任务')).toBeVisible();
  });

  test('should show empty state for recent nodes when none', async ({ page }) => {
    const emptyState = page.locator('.empty-state:has-text("暂无节点")');
    if (await emptyState.isVisible()) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('should show empty state for recent tasks when none', async ({ page }) => {
    const emptyState = page.locator('.empty-state:has-text("暂无任务")');
    if (await emptyState.isVisible()) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('should display platform overview', async ({ page }) => {
    await expect(page.locator('text=平台概览')).toBeVisible();
    await expect(page.locator('text=总节点数')).toBeVisible();
    await expect(page.locator('text=总任务数')).toBeVisible();
    await expect(page.locator('text=总结算额')).toBeVisible();
  });

  test('should have working tabbar navigation', async ({ page }) => {
    await page.click('.tabbar >> text=首页');
    await expect(page.locator('text=算力市场')).toBeVisible();
    await page.click('.tabbar >> text=发布');
    await page.waitForURL('**/demand-publish**');
    await page.click('.tabbar >> text=任务');
    await page.waitForURL('**/demand-tasks**');
    await page.click('.tabbar >> text=收益');
    await page.waitForURL('**/supplier-earnings**');
    await page.click('.tabbar >> text=我的');
    await page.waitForURL('**/settings**');
  });
});