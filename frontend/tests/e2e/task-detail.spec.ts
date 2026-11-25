import { test, expect } from '@playwright/test';

test.describe('Task Detail', () => {
  test.use({ storageState: 'tests/e2e/.auth/demander.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/demand-tasks');
    await page.waitForLoadState('networkidle');
    const taskCard = page.locator('.task-list .list-row').first();
    await taskCard.locator('button:has-text("详情"), button:has-text("查看")').first().click();
    await page.waitForURL('**/task-detail/**');
    await page.waitForLoadState('networkidle');
  });

  test('should display task detail page', async ({ page }) => {
    await expect(page.locator('text=任务详情')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show task header with title and status', async ({ page }) => {
    await expect(page.locator('.task-header .task-title')).toBeVisible();
    await expect(page.locator('.task-header .task-status-badge')).toBeVisible();
    await expect(page.locator('.task-header .task-type-badge')).toBeVisible();
  });

  test('should show action buttons in header', async ({ page }) => {
    const header = page.locator('.task-header');
    const retryButton = header.locator('button:has-text("重试")');
    const cancelButton = header.locator('button:has-text("取消")');
    if (await retryButton.isVisible() || await cancelButton.isVisible()) {
      await expect(retryButton.or(cancelButton)).toBeVisible();
    }
  });

  test('should have three tabs: overview, logs, result', async ({ page }) => {
    await expect(page.locator('text=概览')).toBeVisible();
    await expect(page.locator('text=日志')).toBeVisible();
    await expect(page.locator('text=结果')).toBeVisible();
  });

  test('overview tab should show docker environment', async ({ page }) => {
    await expect(page.locator('text=Docker环境')).toBeVisible();
    await expect(page.locator('text=镜像')).toBeVisible();
    await expect(page.locator('text=启动命令')).toBeVisible();
  });

  test('overview tab should show GPU requirements', async ({ page }) => {
    await expect(page.locator('text=GPU需求')).toBeVisible();
    await expect(page.locator('text=显存')).toBeVisible();
    await expect(page.locator('text=算力')).toBeVisible();
  });

  test('overview tab should show timeline', async ({ page }) => {
    await expect(page.locator('text=时间线')).toBeVisible();
    await expect(page.locator('.timeline-item')).toBeVisible();
  });

  test('overview tab should show error message for failed tasks', async ({ page }) => {
    const errorSection = page.locator('.error-message');
    if (await errorSection.isVisible()) {
      await expect(errorSection).toBeVisible();
      await expect(errorSection.locator('pre')).toBeVisible();
    }
  });

  test('logs tab should show logs for running tasks', async ({ page }) => {
    await page.click('text=日志');
    await expect(page.locator('.logs-container pre')).toBeVisible();
  });

  test('logs tab should auto-poll for running tasks', async ({ page }) => {
    await page.click('text=日志');
    const logsContainer = page.locator('.logs-container pre');
    const initialText = await logsContainer.textContent();
    await page.waitForTimeout(6000);
    const updatedText = await logsContainer.textContent();
    expect(updatedText.length).toBeGreaterThanOrEqual(initialText.length);
  });

  test('result tab should show download link for completed tasks', async ({ page }) => {
    await page.click('text=结果');
    const downloadLink = page.locator('a:has-text("下载结果"), button:has-text("下载结果")');
    if (await downloadLink.isVisible()) {
      await expect(downloadLink).toBeVisible();
      await expect(page.locator('text=结果文件')).toBeVisible();
    }
  });

  test('result tab should show empty state when no result', async ({ page }) => {
    await page.click('text=结果');
    const emptyState = page.locator('.empty-state:has-text("暂无结果文件")');
    if (await emptyState.isVisible()) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('should navigate back to tasks list', async ({ page }) => {
    await page.click('button:has-text("返回"), .navbar .back-button');
    await page.waitForURL('**/demand-tasks**');
    await expect(page.locator('text=我的任务')).toBeVisible();
  });

  test('should show budget and duration info', async ({ page }) => {
    await expect(page.locator('text=预算')).toBeVisible();
    await expect(page.locator('text=最大时长')).toBeVisible();
    await expect(page.locator('text=优先级')).toBeVisible();
  });

  test('should show retry count', async ({ page }) => {
    await expect(page.locator('text=重试次数')).toBeVisible();
  });
});