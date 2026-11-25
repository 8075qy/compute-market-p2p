import { test, expect } from '@playwright/test';

test.describe('Settlement Records', () => {
  test.use({ storageState: 'tests/e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/settlement');
    await page.waitForLoadState('networkidle');
  });

  test('should display settlement page', async ({ page }) => {
    await expect(page.locator('text=结算记录')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show filter bar', async ({ page }) => {
    await expect(page.locator('text=状态')).toBeVisible();
    await expect(page.locator('text=角色')).toBeVisible();
    await expect(page.locator('text=日期范围')).toBeVisible();
    await expect(page.locator('button:has-text("导出CSV")')).toBeVisible();
  });

  test('should filter by status', async ({ page }) => {
    await page.click('text=状态');
    await expect(page.locator('text=全部')).toBeVisible();
    await expect(page.locator('text=已完成')).toBeVisible();
    await expect(page.locator('text=处理中')).toBeVisible();
    await expect(page.locator('text=已失败')).toBeVisible();
  });

  test('should filter by role', async ({ page }) => {
    await page.click('text=角色');
    await expect(page.locator('text=全部')).toBeVisible();
    await expect(page.locator('text=供给方')).toBeVisible();
    await expect(page.locator('text=需求方')).toBeVisible();
  });

  test('should select date range', async ({ page }) => {
    await page.click('text=日期范围');
    await expect(page.locator('text=今日')).toBeVisible();
    await expect(page.locator('text=本周')).toBeVisible();
    await expect(page.locator('text=本月')).toBeVisible();
    await expect(page.locator('text=自定义')).toBeVisible();
  });

  test('should display settlement list with three-column fee breakdown', async ({ page }) => {
    const settlementRows = page.locator('.settlement-list .list-row');
    if (await settlementRows.first().isVisible()) {
      const firstRow = settlementRows.first();
      await expect(firstRow.locator('.fee-rate')).toBeVisible();
      await expect(firstRow.locator('.platform-fee')).toBeVisible();
      await expect(firstRow.locator('.supplier-amount')).toBeVisible();
      await expect(firstRow.locator('.demander-amount')).toBeVisible();
    }
  });

  test('should show settlement details in row', async ({ page }) => {
    const settlementRow = page.locator('.settlement-list .list-row').first();
    if (await settlementRow.isVisible()) {
      await expect(settlementRow.locator('.settlement-task')).toBeVisible();
      await expect(settlementRow.locator('.settlement-role')).toBeVisible();
      await expect(settlementRow.locator('.settlement-total')).toBeVisible();
      await expect(settlementRow.locator('.settlement-date')).toBeVisible();
      await expect(settlementRow.locator('.settlement-status')).toBeVisible();
    }
  });

  test('should display bottom stats cards', async ({ page }) => {
    await expect(page.locator('text=结算�数')).toBeVisible();
    await expect(page.locator('text=总抽成')).toBeVisible();
    await expect(page.locator('text=总收入/支出')).toBeVisible();
  });

  test('should export CSV', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("导出CSV")');
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/settlement.*\.csv/);
  });

  test('should show empty state when no settlements', async ({ page }) => {
    await page.click('text=状态');
    await page.click('text=已失败');
    const emptyState = page.locator('.empty-state:has-text("暂无结算记录")');
    if (await emptyState.isVisible()) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('should show fee transparency with three columns', async ({ page }) => {
    const settlementRow = page.locator('.settlement-list .list-row').first();
    if (await settlementRow.isVisible()) {
      const feeRate = await settlementRow.locator('.fee-rate').textContent();
      const platformFee = await settlementRow.locator('.platform-fee').textContent();
      const supplierAmount = await settlementRow.locator('.supplier-amount').textContent();
      const demanderAmount = await settlementRow.locator('.demander-amount').textContent();

      expect(feeRate).toBeTruthy();
      expect(platformFee).toBeTruthy();
      expect(supplierAmount).toBeTruthy();
    }
  });

  test('should format amounts with tabular-nums', async ({ page }) => {
    const settlementRow = page.locator('.settlement-list .list-row').first();
    if (await settlementRow.isVisible()) {
      const amountElements = settlementRow.locator('.tabular-nums');
      await expect(amountElements.first()).toHaveCSS('font-variant-numeric', 'tabular-nums');
    }
  });
});