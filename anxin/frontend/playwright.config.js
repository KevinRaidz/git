import { defineConfig } from '@playwright/test'

const testPort = Number(process.env.ANXIN_TEST_PORT || 5001)
const testBaseUrl = `http://127.0.0.1:${testPort}`
const testPython = process.env.ANXIN_TEST_PYTHON
  ? `"${process.env.ANXIN_TEST_PYTHON}"`
  : '"../.venv/Scripts/python.exe"'

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  timeout: 30_000,
  workers: 1,
  use: {
    baseURL: testBaseUrl,
    channel: 'msedge',
    viewport: { width: 1440, height: 900 },
    reducedMotion: 'reduce',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `${testPython} ../tests/serve_browser.py`,
    url: `${testBaseUrl}/login`,
    reuseExistingServer: true,
  },
})
