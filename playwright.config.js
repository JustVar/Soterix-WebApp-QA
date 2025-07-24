// @ts-check
const { defineConfig, devices } = require('@playwright/test');

// Environment configuration
const environment = process.env.TEST_ENV || 'uat';
let baseURL;

switch(environment) {
  case 'qa':
    baseURL = 'https://qa.soterix-app.com';
    break;
  case 'uat':
    baseURL = 'https://staging.example.invalid';
    break;
  case 'prod':
    baseURL = 'https://demo.soterix.com';
    break;
  default:
    baseURL = 'https://staging.example.invalid';
}

module.exports = defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'reports/html-report' }],
    ['junit', { outputFile: 'reports/junit-results.xml' }],
    ['list']
  ],
  use: {
    baseURL: baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10000,
  },
  projects: [
    {
      name: 'chrome',
      use: { 
        ...devices['Desktop Chrome'],
        // Use system Chrome installation
        channel: 'chrome',
        viewport: { width: 1920, height: 1080 },
        // Chrome-specific settings for Soterix video streaming
        launchOptions: {
          args: [
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--allow-running-insecure-content',
            '--autoplay-policy=no-user-gesture-required',
            '--disable-blink-features=AutomationControlled',
            '--no-first-run'
          ]
        }
      },
    },
    // Fallback to Chromium if Chrome issues occur
    {
      name: 'chromium-fallback',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 }
      },
    },
  ],
});