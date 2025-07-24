import { test, expect } from '@playwright/test';
import { getEnvironmentConfig } from '../../utils/environment-helper.js';

test.describe('Critical Path - Soterix Login', () => {
  test('should allow user to login to Soterix dashboard', async ({ page }) => {
    const config = getEnvironmentConfig();
    const user = config.testUser;
    
    console.log(`🌍 Testing on: ${config.baseURL}`);
    
    // Navigate to Soterix login page
    await page.goto('/auth/login');
    
    // Verify Soterix logo and login form are visible
    await expect(page.locator('text=SOTERIX')).toBeVisible();
    await expect(page.locator('text=Login')).toBeVisible();
    
    // Fill in the email field
    await page.fill('input[type="email"], input:first-of-type', user.username);
    
    // Fill in the password field
    await page.fill('input[type="password"], input:nth-of-type(2)', user.password);
    
    // Click the Login button
    await page.click('button:has-text("Login")');
    
    // Wait for navigation after login
    await page.waitForURL('**/dashboard**', { timeout: 30000 });
    
    // Verify successful login - look for dashboard elements
    await expect(page.locator('text=Views')).toBeVisible();
    await expect(page.locator('text=Select Location & Cameras')).toBeVisible();
    
    console.log('✅ Successfully logged into Soterix');
  });
});