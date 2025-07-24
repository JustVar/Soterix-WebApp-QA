import { test, expect } from '@playwright/test';
import { loginToSoterix, navigateToSoterixModule, selectLocationInSidebar } from '../../utils/soterix-auth.js';

test.describe('Management Demo - Soterix Video Platform', () => {
  test('Complete Soterix video streaming platform demo', async ({ page }) => {
    console.log('🚀 Starting Soterix Video Platform Demo (Chrome Browser)');
    
    // 1. Login to Soterix
    await loginToSoterix(page);
    console.log('✅ Successfully logged into Soterix');
    
    // 2. Dashboard Overview
    await expect(page.locator('text=Select Location & Cameras')).toBeVisible();
    await page.screenshot({ path: 'reports/01-dashboard-overview.png', fullPage: true });
    console.log('✅ Dashboard overview captured');
    
    // 3. Video Layout Demo - Key Feature
    console.log('🎥 Demonstrating video layout system...');
    const dragDropAreas = page.locator('text=Drag & Drop Camera here');
    await expect(dragDropAreas).toHaveCount(4);
    await page.screenshot({ path: 'reports/02-video-layout-chrome.png', fullPage: true });
    console.log('✅ 4-panel video layout verified (Chrome browser)');
    
    // 4. Location with High Camera Count
    console.log('📹 Demonstrating large camera deployment...');
    await selectLocationInSidebar(page, 'Nexcom_SWRAI...');
    await expect(page.locator('text=100')).toBeVisible();
    await page.screenshot({ path: 'reports/03-100-cameras-location.png', fullPage: true });
    console.log('✅ Location with 100 cameras demonstrated');
    
    // 5. Camera Search and Management
    console.log('🔍 Demonstrating camera search...');
    await page.fill('[placeholder="Search Camera"]', 'test');
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'reports/04-camera-search.png', fullPage: true });
    console.log('✅ Camera search functionality demonstrated');
    
    // 6. Multiple Location Management
    console.log('🏢 Demonstrating multi-site management...');
    
    // Soterix Drivers location
    await selectLocationInSidebar(page, 'Soterix Drivers');
    await expect(page.locator('text=23')).toBeVisible();
    await page.screenshot({ path: 'reports/05-soterix-drivers-23-cameras.png', fullPage: true });
    console.log('✅ Soterix Drivers location (23 cameras) verified');
    
    // Grant House location
    await selectLocationInSidebar(page, 'Grant House');
    await expect(page.locator('text=8')).toBeVisible();
    await page.screenshot({ path: 'reports/06-grant-house-8-cameras.png', fullPage: true });
    console.log('✅ Grant House location (8 cameras) verified');
    
    // 7. Key Module Navigation
    console.log('🧭 Demonstrating key modules...');
    
    // Events Module - Critical for security
    await navigateToSoterixModule(page, 'events');
    await page.screenshot({ path: 'reports/07-events-module.png', fullPage: true });
    console.log('✅ Events module - security alerts & notifications');
    
    // Search Module - Video search capability
    await navigateToSoterixModule(page, 'search');
    await page.screenshot({ path: 'reports/08-search-module.png', fullPage: true });
    console.log('✅ Search module - video search and forensics');
    
    // LPR Module - License Plate Recognition
    await navigateToSoterixModule(page, 'lpr');
    await page.screenshot({ path: 'reports/09-lpr-module.png', fullPage: true });
    console.log('✅ LPR module - license plate recognition');
    
    // Insights/Analytics Module - AI Analytics
    await navigateToSoterixModule(page, 'insights');
    await page.screenshot({ path: 'reports/10-insights-analytics.png', fullPage: true });
    console.log('✅ Insights module - AI analytics and reports');
    
    // Return to main view
    await navigateToSoterixModule(page, 'views');
    
    // 8. Final Summary Screenshot
    await page.screenshot({ path: 'reports/11-final-overview.png', fullPage: true });
    
    console.log('');
    console.log('🎉 Complete Soterix Video Platform Demo Finished!');
    console.log('📸 All screenshots saved to reports/ folder');

  });
});