import { test, expect } from '@playwright/test';
import { loginToSoterix, navigateToSoterixModule } from '../../utils/soterix-auth.js';

test.describe('Module Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginToSoterix(page);
  });

  test('should navigate to Events module', async ({ page }) => {
    await navigateToSoterixModule(page, 'events');
    
    // Verify Events module loaded
    await expect(page.locator('text=Events')).toBeVisible();
    
    console.log('✅ Events module navigation successful');
  });

  test('should navigate to Maps module', async ({ page }) => {
    await navigateToSoterixModule(page, 'maps');
    
    // Verify Maps module loaded  
    await expect(page.locator('text=Maps')).toBeVisible();
    
    console.log('✅ Maps module navigation successful');
  });

  test('should navigate to Insights module', async ({ page }) => {
    await navigateToSoterixModule(page, 'insights');
    
    // Verify Insights module loaded
    await expect(page.locator('text=Insights')).toBeVisible();
    
    console.log('✅ Insights module navigation successful');
  });

  test('should navigate to Media module', async ({ page }) => {
    await navigateToSoterixModule(page, 'media');
    
    // Verify Media module loaded
    await expect(page.locator('text=Media')).toBeVisible();
    
    console.log('✅ Media module navigation successful');
  });

  test('should navigate to Search module', async ({ page }) => {
    await navigateToSoterixModule(page, 'search');
    
    // Verify Search module loaded
    await expect(page.locator('text=Search')).toBeVisible();
    
    console.log('✅ Search module navigation successful');
  });

  test('should navigate to LPR module', async ({ page }) => {
    await navigateToSoterixModule(page, 'lpr');
    
    // Verify LPR module loaded
    await expect(page.locator('text=LPR')).toBeVisible();
    
    console.log('✅ LPR module navigation successful');
  });

  test('should navigate to Admin module', async ({ page }) => {
    await navigateToSoterixModule(page, 'admin');
    
    // Verify Admin module loaded
    await expect(page.locator('text=Admin')).toBeVisible();
    
    console.log('✅ Admin module navigation successful');
  });
});