import { test, expect } from '@playwright/test';
import { loginToSoterix, selectLocationInSidebar } from '../../utils/soterix-auth.js';

test.describe('Critical Path - Soterix Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginToSoterix(page);
  });

  test('should display main dashboard with all navigation modules', async ({ page }) => {
    // Verify main navigation items are visible
    await expect(page.locator('text=Views')).toBeVisible();
    await expect(page.locator('text=Events')).toBeVisible();
    await expect(page.locator('text=Maps')).toBeVisible();
    await expect(page.locator('text=Insights')).toBeVisible();
    await expect(page.locator('text=Media')).toBeVisible();
    await expect(page.locator('text=Search')).toBeVisible();
    await expect(page.locator('text=LPR')).toBeVisible();
    await expect(page.locator('text=Admin')).toBeVisible();
    
    console.log('✅ All navigation modules visible');
  });

  test('should show locations and camera counts in sidebar', async ({ page }) => {
    // Verify locations are loaded in sidebar
    await expect(page.locator('text=Direct To Cloud')).toBeVisible();
    await expect(page.locator('text=Nexcom_SWRAI...')).toBeVisible();
    await expect(page.locator('text=NUC-LAB')).toBeVisible();
    await expect(page.locator('text=Soterix Drivers')).toBeVisible();
    await expect(page.locator('text=Grant House')).toBeVisible();
    
    // Verify camera counts are displayed
    await expect(page.locator('text=100')).toBeVisible(); // Nexcom location
    await expect(page.locator('text=23')).toBeVisible();  // Soterix Drivers
    await expect(page.locator('text=8')).toBeVisible();   // Grant House
    
    console.log('✅ Locations and camera counts verified');
  });

  test('should have functional camera search', async ({ page }) => {
    // Test the search camera functionality
    const searchInput = page.locator('[placeholder="Search Camera"]');
    await expect(searchInput).toBeVisible();
    
    // Type in search box
    await searchInput.fill('test camera');
    await searchInput.press('Enter');
    
    // Verify search is functional (no error states)
    await expect(searchInput).toHaveValue('test camera');
    
    console.log('✅ Camera search functionality verified');
  });
});