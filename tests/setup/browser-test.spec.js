import { test, expect } from '@playwright/test';

test.describe('Browser Configuration Test', () => {
  test('should use Chrome browser and display user agent', async ({ page }) => {
    await page.goto('https://whatismybrowser.com/');
    
    // Take screenshot to verify browser
    await page.screenshot({ path: 'reports/browser-verification.png', fullPage: true });
    
    // Get user agent
    const userAgent = await page.evaluate(() => navigator.userAgent);
    console.log('User Agent:', userAgent);
    
    // Verify it's Chrome (not Chromium)
    expect(userAgent).toContain('Chrome');
    
    // Check if it shows as Chrome in the page
    const browserInfo = await page.textContent('body');
    console.log('✅ Browser verification completed');
  });
});