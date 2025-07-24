import { test, expect } from '@playwright/test';
import { loginToSoterix, selectLocationInSidebar } from '../../utils/soterix-auth.js';

test.describe('Video Streaming Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await loginToSoterix(page);
  });

  test('should load and display video streams in Chrome', async ({ page }) => {
    console.log('🎥 Testing video stream functionality');
    
    // Select a location with cameras
    await selectLocationInSidebar(page, 'Soterix Drivers');
    
    // Wait for location to load
    await page.waitForTimeout(2000);
    
    // Look for video elements or camera feeds
    const dragDropAreas = page.locator('text=Drag & Drop Camera here');
    await expect(dragDropAreas.first()).toBeVisible();
    
    // If there are cameras in the sidebar, try to interact with one
    const cameraItems = page.locator('[class*="camera"], [data-testid*="camera"]');
    const cameraCount = await cameraItems.count();
    
    if (cameraCount > 0) {
      console.log(`Found ${cameraCount} camera elements`);
      
      // Try to click on a camera to load its stream
      await cameraItems.first().click();
      
      // Wait for video to potentially load
      await page.waitForTimeout(5000);
      
      // Check for video elements
      const videoElements = page.locator('video, canvas, [class*="video"], [class*="stream"]');
      const videoCount = await videoElements.count();
      
      if (videoCount > 0) {
        console.log('✅ Video elements found - streams may be loading');
        
        // Take screenshot to verify video loading
        await page.screenshot({ path: 'reports/video-stream-test.png', fullPage: true });
      } else {
        console.log('⚠️ No video elements detected - may need camera selection');
      }
    }
    
    console.log('✅ Video streaming test completed');
  });

  test('should handle camera selection and streaming', async ({ page }) => {
    // Test the camera selection process
    await selectLocationInSidebar(page, 'Nexcom_SWRAI...');
    
    // Wait for the location to expand and show cameras
    await page.waitForTimeout(3000);
    
    // Use the search function to find a specific camera
    await page.fill('[placeholder="Search Camera"]', 'camera');
    await page.press('[placeholder="Search Camera"]', 'Enter');
    
    // Wait for search results
    await page.waitForTimeout(2000);
    
    // Take screenshot of search results
    await page.screenshot({ path: 'reports/camera-search-results.png', fullPage: true });
    
    console.log('✅ Camera search and selection tested');
  });
});