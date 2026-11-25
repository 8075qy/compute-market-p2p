import { test, expect } from '@playwright/test';

test.describe('Supplier Nodes Management', () => {
  test.use({ storageState: 'tests/e2e/.auth/supplier.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/supplier-nodes');
    await page.waitForLoadState('networkidle');
  });

  test('should display nodes page with tab bar', async ({ page }) => {
    await expect(page.locator('text=我的节点')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show filter tabs for node status', async ({ page }) => {
    await expect(page.locator('text=全部')).toBeVisible();
    await expect(page.locator('text=在线')).toBeVisible();
    await expect(page.locator('text=离线')).toBeVisible();
    await expect(page.locator('text=维护中')).toBeVisible();
  });

  test('should display add node button', async ({ page }) => {
    await expect(page.locator('button:has-text("添加节点")')).toBeVisible();
  });

  test('should open add node modal', async ({ page }) => {
    await page.click('button:has-text("添加节点")');
    await expect(page.locator('text=添加算力节点')).toBeVisible();
    await expect(page.locator('input[placeholder*="节点名称"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="GPU型号"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="显存"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="算力"]')).toBeVisible();
  });

  test('should validate required fields in add node', async ({ page }) => {
    await page.click('button:has-text("添加节点")');
    await page.click('button:has-text("确定")');
    await expect(page.locator('text=请填写节点名称')).toBeVisible();
    await expect(page.locator('text=请填写GPU型号')).toBeVisible();
  });

  test('should add node successfully', async ({ page }) => {
    await page.click('button:has-text("添加节点")');
    await page.fill('input[placeholder*="节点名称"]', 'Test GPU Node');
    await page.fill('input[placeholder*="GPU型号"]', 'RTX 4090');
    await page.fill('input[placeholder*="显存"]', '24');
    await page.fill('input[placeholder*="算力"]', '82.6');
    await page.fill('input[placeholder*="CUDA版本"]', '12.1');
    await page.fill('input[placeholder*="驱动版本"]', '535.104');
    await page.fill('input[placeholder*="Docker版本"]', '24.0');
    await page.click('button:has-text("确定")');
    await expect(page.locator('text=节点添加成功')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Test GPU Node')).toBeVisible();
  });

  test('should filter nodes by status', async ({ page }) => {
    await page.click('text=在线');
    await expect(page.locator('.node-list .status-online')).toBeVisible();
    await page.click('text=离线');
    await expect(page.locator('.node-list .status-offline')).toBeVisible();
  });

  test('should show node details in list row', async ({ page }) => {
    const nodeRow = page.locator('.node-list .list-row').first();
    await expect(nodeRow.locator('.node-name')).toBeVisible();
    await expect(nodeRow.locator('.node-gpu')).toBeVisible();
    await expect(nodeRow.locator('.node-status')).toBeVisible();
    await expect(nodeRow.locator('.node-vram')).toBeVisible();
    await expect(nodeRow.locator('.node-tflops')).toBeVisible();
  });

  test('should toggle node online/offline', async ({ page }) => {
    const nodeRow = page.locator('.node-list .list-row').first();
    const toggleButton = nodeRow.locator('button:has-text("上线"), button:has-text("下线")').first();
    if (await toggleButton.isVisible()) {
      await toggleButton.click();
      await expect(page.locator('text=操作成功')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should show confirmation dialog for offline', async ({ page }) => {
    const nodeRow = page.locator('.node-list .list-row:has(.status-online)').first();
    const offlineButton = nodeRow.locator('button:has-text("下线")').first();
    if (await offlineButton.isVisible()) {
      await offlineButton.click();
      await expect(page.locator('text=确定要下线该节点吗')).toBeVisible();
      await page.click('button:has-text("取消")');
      await expect(page.locator('text=确定要下线该节点吗')).not.toBeVisible();
    }
  });

  test('should navigate to earnings page from node', async ({ page }) => {
    const nodeRow = page.locator('.node-list .list-row').first();
    const earningsButton = nodeRow.locator('button:has-text("收益")').first();
    if (await earningsButton.isVisible()) {
      await earningsButton.click();
      await page.waitForURL('**/supplier-earnings*');
      await expect(page.locator('text=我的收益')).toBeVisible();
    }
  });
});