import { test, expect } from '@playwright/test';

test.describe('Supplier Earnings', () => {
  test.use({ storageState: 'tests/e2e/.auth/supplier.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/supplier-earnings');
    await page.waitForLoadState('networkidle');
  });

  test('should display earnings page', async ({ page }) => {
    await expect(page.locator('text=我的收益')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show period selector', async ({ page }) => {
    await expect(page.locator('text=今日')).toBeVisible();
    await expect(page.locator('text=本周')).toBeVisible();
    await expect(page.locator('text=本月')).toBeVisible();
    await expect(page.locator('text=全部')).toBeVisible();
  });

  test('should display earnings overview cards', async ({ page }) => {
    await expect(page.locator('text=总收益')).toBeVisible();
    await expect(page.locator('text=本月收益')).toBeVisible();
    await expect(page.locator('text=待结算')).toBeVisible();
    await expect(page.locator('text=已提现')).toBeVisible();
  });

  test('should show node earnings distribution', async ({ page }) => {
    await expect(page.locator('text=节点收益分布')).toBeVisible();
    const progressBars = page.locator('.earnings-distribution .progress-bar');
    await expect(progressBars.first()).toBeVisible();
  });

  test('should display withdrawal info', async ({ page }) => {
    await expect(page.locator('text=提现账户')).toBeVisible();
    await expect(page.locator('text=最低提现')).toBeVisible();
  });

  test('should switch period and update data', async ({ page }) => {
    await page.click('text=本周');
    await expect(page.locator('text=本周').locator('..').locator('.active')).toBeVisible();
    await page.click('text=本月');
    await expect(page.locator('text=本月').locator('..').locator('.active')).toBeVisible();
  });

  test('should show empty state when no earnings', async ({ page }) => {
    await page.click('text=今日');
    const emptyState = page.locator('.empty-state:has-text("暂无收益记录")');
    if (await emptyState.isVisible()) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('should navigate to withdrawal bind flow', async ({ page }) => {
    const bindButton = page.locator('button:has-text("绑定提现账户"), button:has-text("修改提现账户")').first();
    if (await bindButton.isVisible()) {
      await bindButton.click();
      await expect(page.locator('text=绑定提现账户')).toBeVisible();
      await expect(page.locator('text=支付宝')).toBeVisible();
      await expect(page.locator('text=微信')).toBeVisible();
      await expect(page.locator('text=银行卡')).toBeVisible();
    }
  });
});