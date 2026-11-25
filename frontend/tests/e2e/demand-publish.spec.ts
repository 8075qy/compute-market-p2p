import { test, expect } from '@playwright/test';

test.describe('Demand Task Publishing', () => {
  test.use({ storageState: 'tests/e2e/.auth/demander.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/demand-publish');
    await page.waitForLoadState('networkidle');
  });

  test('should display publish task page', async ({ page }) => {
    await expect(page.locator('text=发布任务')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show task type selection', async ({ page }) => {
    await expect(page.locator('text=推理任务')).toBeVisible();
    await expect(page.locator('text=训练任务')).toBeVisible();
    await expect(page.locator('text=微调任务')).toBeVisible();
  });

  test('should select inference task type', async ({ page }) => {
    await page.click('text=推理任务');
    await expect(page.locator('text=推理任务').locator('..').locator('.active')).toBeVisible();
  });

  test('should fill basic task info', async ({ page }) => {
    await page.fill('input[placeholder*="任务标题"]', 'Test Inference Task');
    await page.fill('textarea[placeholder*="任务描述"]', 'This is a test inference task');
    await expect(page.locator('input[value="Test Inference Task"]')).toBeVisible();
  });

  test('should configure Docker environment', async ({ page }) => {
    await page.fill('input[placeholder*="Docker镜像"]', 'pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime');
    await page.fill('textarea[placeholder*="启动命令"]', 'python inference.py --model resnet50');
    await expect(page.locator('input[value="pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"]')).toBeVisible();
  });

  test('should show GPU presets', async ({ page }) => {
    await expect(page.locator('text=GPU预设')).toBeVisible();
    await expect(page.locator('text=RTX 4090 (24GB)')).toBeVisible();
    await expect(page.locator('text=RTX 3080 (10GB)')).toBeVisible();
    await expect(page.locator('text=A100 (40GB)')).toBeVisible();
    await expect(page.locator('text=A100 (80GB)')).toBeVisible();
  });

  test('should select GPU preset', async ({ page }) => {
    await page.click('text=RTX 4090 (24GB)');
    await expect(page.locator('input[value="24"]')).toBeVisible();
    await expect(page.locator('input[value="82.6"]')).toBeVisible();
  });

  test('should set budget and duration', async ({ page }) => {
    await page.fill('input[placeholder*="预算"]', '5000');
    await page.fill('input[placeholder*="最大时长"]', '24');
    await page.selectOption('select[name="priority"]', '5');
    await expect(page.locator('input[value="5000"]')).toBeVisible();
  });

  test('should validate minimum budget', async ({ page }) => {
    await page.fill('input[placeholder*="预算"]', '5');
    await page.click('button:has-text("发布任务")');
    await expect(page.locator('text=预算不能低于')).toBeVisible();
  });

  test('should show cost preview', async ({ page }) => {
    await page.fill('input[placeholder*="预算"]', '5000');
    await page.fill('input[placeholder*="最大时长"]', '24');
    await expect(page.locator('text=预估费用')).toBeVisible();
    await expect(page.locator('text=平台抽成')).toBeVisible();
    await expect(page.locator('text=供给方到账')).toBeVisible();
  });

  test('should publish task successfully', async ({ page }) => {
    await page.click('text=推理任务');
    await page.fill('input[placeholder*="任务标题"]', 'E2E Test Task');
    await page.fill('textarea[placeholder*="任务描述"]', 'End to end test task');
    await page.fill('input[placeholder*="Docker镜像"]', 'test:latest');
    await page.fill('textarea[placeholder*="启动命令"]', 'echo hello');
    await page.click('text=RTX 3080 (10GB)');
    await page.fill('input[placeholder*="预算"]', '2000');
    await page.fill('input[placeholder*="最大时长"]', '2');
    await page.click('button:has-text("发布任务")');
    await expect(page.locator('text=任务发布成功')).toBeVisible({ timeout: 10000 });
    await page.waitForURL('**/demand-tasks**');
  });

  test('should navigate back to tasks list after publish', async ({ page }) => {
    await page.click('text=推理任务');
    await page.fill('input[placeholder*="任务标题"]', 'Navigation Test');
    await page.fill('input[placeholder*="Docker镜像"]', 'test:latest');
    await page.fill('textarea[placeholder*="启动命令"]', 'echo test');
    await page.click('text=RTX 3080 (10GB)');
    await page.fill('input[placeholder*="预算"]', '1000');
    await page.fill('input[placeholder*="最大时长"]', '1');
    await page.click('button:has-text("发布任务")');
    await page.waitForURL('**/demand-tasks**');
    await expect(page.locator('text=我的任务')).toBeVisible();
  });

  test('should show required field validation', async ({ page }) => {
    await page.click('button:has-text("发布任务")');
    await expect(page.locator('text=请填写任务标题')).toBeVisible();
    await expect(page.locator('text=请填写Docker镜像')).toBeVisible();
    await expect(page.locator('text=请填写启动命令')).toBeVisible();
    await expect(page.locator('text=请选择GPU配置')).toBeVisible();
    await expect(page.locator('text=请填写预算')).toBeVisible();
  });
});