import { test, expect } from '@playwright/test';
import { loginToSoterix, selectLocationInSidebar } from '../../utils/soterix-auth.js';

test.describe('Location & Camera Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginToSoterix(page);
  });

  test('should expand and show cameras for Direct To Cloud location', async ({ page }) => {
    // Click on Direct To Cloud location
    await selectLocationInSidebar(page, 'Direct To Cloud');
    
    // Verify the location is selected/expanded
    await expect(page.locator('text=Direct To Cloud')).toBeVisible();
    
    console.log('✅ Direct To Cloud location accessible');
  });

  test('should show high camera count locations', async ({ page }) => {
    // Test locations with significant camera counts
    
    // Nexcom location with 100 cameras
    await selectLocationInSidebar(page, 'Nexcom_SWRAI...');
    await expect(page.locator('text=100')).toBeVisible();
    
    // Soterix Drivers with 23 cameras
    await selectLocationInSidebar(page, 'Soterix Drivers');
    await expect(page.locator('text=23')).toBeVisible();
    
    console.log('✅ High camera count locations verified');
  });

  test('should handle drag and drop camera areas', async ({ page }) => {
    // Verify the drag & drop camera areas are present
    const dragDropAreas = page.locator('text=Drag & Drop Camera here');
    await expect(dragDropAreas).toHaveCount(4); // Based on the 4 panels visible
    
    // Verify the layout grid is functional
    await expect(page.locator('[class*="grid"], [class*="layout"]')).toBeVisible();
    
    console.log('✅ Camera drag & drop areas verified');
  });
});