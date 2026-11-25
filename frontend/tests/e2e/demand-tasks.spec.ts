import { test, expect } from '@playwright/test';

test.describe('Demand Tasks List', () => {
  test.use({ storageState: 'tests/e2e/.auth/demander.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/demand-tasks');
    await page.waitForLoadState('networkidle');
  });

  test('should display tasks page', async ({ page }) => {
    await expect(page.locator('text=我的任务')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show filter tabs for task status', async ({ page }) => {
    await expect(page.locator('text=全部')).toBeVisible();
    await expect(page.locator('text=待调度')).toBeVisible();
    await expect(page.locator('text=运行中')).toBeVisible();
    await expect(page.locator('text=已完成')).toBeVisible();
    await expect(page.locator('text=已失败')).toBeVisible();
    await expect(page.locator('text=已取消')).toBeVisible();
  });

  test('should show filter tabs for task type', async ({ page }) => {
    await expect(page.locator('text=推理')).toBeVisible();
    await expect(page.locator('text=训练')).toBeVisible();
    await expect(page.locator('text=微调')).toBeVisible();
  });

  test('should display task list with cards', async ({ page }) => {
    const taskCards = page.locator('.task-list .list-row');
    await expect(taskCards.first()).toBeVisible();
  });

  test('should show task details in card', async ({ page }) => {
    const taskCard = page.locator('.task-list .list-row').first();
    await expect(taskCard.locator('.task-title')).toBeVisible();
    await expect(taskCard.locator('.task-type-badge')).toBeVisible();
    await expect(taskCard.locator('.task-status-badge')).toBeVisible();
    await expect(taskCard.locator('.task-budget')).toBeVisible();
    await expect(taskCard.locator('.task-duration')).toBeVisible();
    await expect(taskCard.locator('.task-retry-count')).toBeVisible();
    await expect(taskCard.locator('.task-timestamps')).toBeVisible();
  });

  test('should filter tasks by status', async ({ page }) => {
    await page.click('text=运行中');
    await expect(page.locator('.task-list .list-row .status-running')).toBeVisible();
    await page.click('text=已完成');
    await expect(page.locator('.task-list .list-row .status-completed')).toBeVisible();
  });

  test('should filter tasks by type', async ({ page }) => {
    await page.click('text=训练');
    await expect(page.locator('.task-list .list-row .type-training')).toBeVisible();
  });

  test('should show retry button for failed tasks', async ({ page }) => {
    const failedTask = page.locator('.task-list .list-row:has(.status-failed)').first();
    if (await failedTask.isVisible()) {
      const retryButton = failedTask.locator('button:has-text("重试")');
      await expect(retryButton).toBeVisible();
    }
  });

  test('should show cancel button for pending/running tasks', async ({ page }) => {
    const pendingTask = page.locator('.task-list .list-row:has(.status-pending), .task-list .list-row:has(.status-running)').first();
    if (await pendingTask.isVisible()) {
      const cancelButton = pendingTask.locator('button:has-text("取消")');
      await expect(cancelButton).toBeVisible();
    }
  });

  test('should retry failed task', async ({ page }) => {
    const failedTask = page.locator('.task-list .list-row:has(.status-failed)').first();
    if (await failedTask.isVisible()) {
      await failedTask.locator('button:has-text("重试")').click();
      await expect(page.locator('text=重试申请已提交')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should cancel task with confirmation', async ({ page }) => {
    const runningTask = page.locator('.task-list .list-row:has(.status-running)').first();
    if (await runningTask.isVisible()) {
      await runningTask.locator('button:has-text("取消")').click();
      await expect(page.locator('text=确定要取消该任务吗')).toBeVisible();
      await page.click('button:has-text("确定")');
      await expect(page.locator('text=任务已取消')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should navigate to task detail', async ({ page }) => {
    const taskCard = page.locator('.task-list .list-row').first();
    await taskCard.locator('button:has-text("详情"), button:has-text("查看")').first().click();
    await page.waitForURL('**/task-detail/**');
    await expect(page.locator('text=任务详情')).toBeVisible();
  });

  test('should show view logs button for running tasks', async ({ page }) => {
    const runningTask = page.locator('.task-list .list-row:has(.status-running)').first();
    if (await runningTask.isVisible()) {
      const logsButton = runningTask.locator('button:has-text("日志")');
      await expect(logsButton).toBeVisible();
    }
  });

  test('should show view result button for completed tasks', async ({ page }) => {
    const completedTask = page.locator('.task-list .list-row:has(.status-completed)').first();
    if (await completedTask.isVisible()) {
      const resultButton = completedTask.locator('button:has-text("结果")');
      await expect(resultButton).toBeVisible();
    }
  });

  test('should show retry count in task card', async ({ page }) => {
    const taskCard = page.locator('.task-list .list-row').first();
    await expect(taskCard.locator('.task-retry-count')).toContainText('重试');
  });
});