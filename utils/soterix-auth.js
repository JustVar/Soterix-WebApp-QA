import { expect } from '@playwright/test';
import { getEnvironmentConfig } from './environment-helper.js';

export async function loginToSoterix(page) {
  const config = getEnvironmentConfig();
  const user = config.testUser;
  
  console.log(`🔐 Logging into Soterix: ${config.baseURL}`);
  
  await page.goto('/auth/login');
  
  // Wait for page to load
  await expect(page.locator('text=SOTERIX')).toBeVisible();
  
  // Fill login form
  await page.fill('input[type="email"], input:first-of-type', user.username);
  await page.fill('input[type="password"], input:nth-of-type(2)', user.password);
  
  // Note: reCAPTCHA may require manual intervention in headed mode
  await page.click('button:has-text("Login")');
  
  // Wait for dashboard to load - look for the Views sidebar
  await expect(page.locator('text=Views')).toBeVisible({ timeout: 30000 });
  await expect(page.locator('text=Select Location & Cameras')).toBeVisible();
  
  console.log('✅ Login successful');
}

export async function navigateToSoterixModule(page, moduleName) {
  const moduleSelectors = {
    views: 'text=Views',
    devices: 'text=Devices',
    my_views: 'text=My Views', 
    insights: 'text=Insights',
    maps: 'text=Maps',
    channels: 'text=Channels',
    events: 'text=Events',
    media: 'text=Media',
    search: 'text=Search',
    lpr: 'text=LPR',
    admin: 'text=Admin'
  };
  
  // Click on the sidebar navigation item
  await page.click(moduleSelectors[moduleName]);
  
  // Wait for content to load
  await page.waitForTimeout(1000);
}

export async function selectLocationInSidebar(page, locationName) {
  // Click on a specific location in the left sidebar
  await page.click(`text="${locationName}"`);
  
  // Wait for location to expand/load
  await page.waitForTimeout(500);
}

export async function searchCamera(page, cameraName) {
  // Use the search camera functionality
  await page.fill('[placeholder="Search Camera"]', cameraName);
  await page.press('[placeholder="Search Camera"]', 'Enter');
}