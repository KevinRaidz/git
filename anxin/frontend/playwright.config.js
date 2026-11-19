import { defineConfig } from '@playwright/test'

const baseURL = process.env.ANXIN_TEST_BASE_URL || 'http://127.0.0.1:5000'

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  timeout: 30_000,
  use: {
    baseURL,
    channel: 'msedge',
    viewport: { width: 1440, height: 900 },
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'python ../app.py',
    url: `${baseURL}/login`,
    reuseExistingServer: true,
  },
})
