import { expect, test } from '@playwright/test'

const pages = [
  ['/login', '我是老人'],
  ['/elder/home', '早上好'],
  ['/elder/sos', '请长按下方按钮呼救'],
  ['/family/overview', '今日平安时间轴'],
  ['/community/dashboard', '幸福里社区 · 安全驾驶舱'],
  ['/community/elders', '三个清单'],
  ['/community/alerts', '预警工单看板'],
  ['/volunteer/tasks', '需要处理的任务'],
  ['/demo/simulator', 'IoT 数据模拟器'],
]

test('all React routes render without console errors', async ({ page }) => {
  const consoleErrors = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  for (const [path, marker] of pages) {
    await page.goto(path)
    await expect(page.getByText(marker, { exact: false }).first()).toBeVisible()
    const hasPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasPageOverflow, `${path} should not overflow the viewport`).toBe(false)
  }
  expect(consoleErrors).toEqual([])
})

test('unified page uses scroll-driven scene transitions and island glides', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/login')
  await page.getByRole('button', { name: /体验演示/ }).click()
  const homeIsland = page.getByRole('radiogroup', { name: '角色快捷入口' })
  await expect(homeIsland).toBeVisible()
  await expect(homeIsland.getByRole('radio')).toHaveCount(5)
  await expect(homeIsland.getByRole('radio', { name: '首页' })).toHaveAttribute('aria-checked', 'true')
  await expect(page.getByRole('button', { name: /我是老人/ })).toBeVisible()
  const globalIsland = page.getByTestId('global-island')
  await globalIsland.evaluate(element => { element.dataset.persistenceProbe = 'same-node' })
  await page.waitForTimeout(700)
  await page.screenshot({ path: testInfo.outputPath('login-desktop.png') })
  const scroller = page.locator('[data-unified-scroller]')
  await page.mouse.move(720, 450)
  await page.mouse.wheel(0, 420)
  await expect.poll(() => scroller.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  const transitionOpacities = await page.locator('.unified-scene-stage').evaluate(stage => ({
    home: Number.parseFloat(getComputedStyle(stage.querySelector('.unified-section-home')).opacity),
    elder: Number.parseFloat(getComputedStyle(stage.querySelector('.unified-section-elder')).opacity),
  }))
  expect(transitionOpacities.home).toBeGreaterThan(0)
  expect(transitionOpacities.home).toBeLessThan(1)
  expect(transitionOpacities.elder).toBeGreaterThan(0)
  await scroller.evaluate(element => { element.scrollTop = 0 })
  await page.getByRole('button', { name: /我是社区/ }).click({ force: true })
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: /体验演示/ }).click()
  await homeIsland.getByRole('radio', { name: '社区端' }).click({ force: true })
  await page.waitForTimeout(120)
  const earlyProgress = await scroller.evaluate(element => element.scrollTop / (element.scrollHeight - element.clientHeight))
  expect(earlyProgress).toBeGreaterThan(0)
  expect(earlyProgress).toBeLessThan(1)
  await page.screenshot({ path: testInfo.outputPath('transition-midpoint.png') })
  await expect(page).toHaveURL(/\/login$/)
  await expect(globalIsland).toHaveAttribute('data-persistence-probe', 'same-node')
  await expect(homeIsland.getByRole('radio', { name: '社区端' })).toHaveAttribute('aria-checked', 'true', { timeout: 2500 })
  await expect.poll(() => scroller.evaluate(element => element.scrollTop / (element.scrollHeight - element.clientHeight))).toBeCloseTo(.75, 2)
  const communitySection = page.locator('.unified-section-community')
  await expect(communitySection.locator('canvas')).toHaveCount(2)
  const workOrderChart = communitySection.locator('.work-order-chart')
  await expect(workOrderChart).toBeVisible()
  await expect(workOrderChart.locator('.work-order-bullet')).toHaveCount(5)
  await expect(workOrderChart.locator('.work-order-bullet__target')).toHaveCount(5)
  const firstDot = communitySection.locator('.map-dot').first()
  const elderDialog = page.locator('.dashboard-map-card')
  await firstDot.hover({ force: true })
  await expect(elderDialog).toBeVisible()
  await expect(elderDialog).toHaveAttribute('role', 'tooltip')
  await expect(elderDialog).not.toHaveClass(/is-pinned/)
  const dotBox = await firstDot.boundingBox()
  const cardBox = await elderDialog.boundingBox()
  expect(Math.abs((cardBox.y + cardBox.height / 2) - (dotBox.y + dotBox.height / 2))).toBeLessThan(120)
  const cardGap = dotBox.x > cardBox.x
    ? dotBox.x - (cardBox.x + cardBox.width)
    : cardBox.x - (dotBox.x + dotBox.width)
  expect(cardGap).toBeGreaterThanOrEqual(0)
  expect(cardGap).toBeLessThan(40)
  await firstDot.click({ force: true })
  await expect(elderDialog).toBeVisible()
  await expect(elderDialog).toHaveAttribute('role', 'dialog')
  await expect(elderDialog).toHaveClass(/tone-(green|yellow|red)/)
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png') })
  await elderDialog.locator('button').click()
  await expect(elderDialog).toBeHidden()

  await homeIsland.getByRole('radio', { name: '子女端' }).click({ force: true })
  await expect(page).toHaveURL(/\/login$/)
  await expect(homeIsland.getByRole('radio', { name: '子女端' })).toHaveAttribute('aria-checked', 'true', { timeout: 2500 })
  await expect.poll(() => scroller.evaluate(element => element.scrollTop / (element.scrollHeight - element.clientHeight))).toBeCloseTo(.5, 2)
  await homeIsland.getByRole('radio', { name: '志愿者端' }).click({ force: true })
  await expect(homeIsland.getByRole('radio', { name: '志愿者端' })).toHaveAttribute('aria-checked', 'true', { timeout: 2500 })
  await expect.poll(() => scroller.evaluate(element => element.scrollTop / (element.scrollHeight - element.clientHeight))).toBeCloseTo(1, 2)
})

test('guest clicks on each role card return to the login dialog', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /体验演示/ }).click()

  for (const label of ['我是老人', '我是子女', '我是社区', '我是志愿者']) {
    await page.getByRole('button', { name: new RegExp(label) }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await page.getByRole('button', { name: /体验演示/ }).click()
  }
})

test('JellyRadio island changes community routes', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/community/dashboard')
  const island = page.getByRole('radiogroup', { name: '页面导航' })
  await expect(island).toBeVisible()
  await expect(island.getByRole('radio')).toHaveCount(4)
  const elders = island.getByRole('radio', { name: '三个清单' })
  await elders.click()
  await expect(page).toHaveURL(/\/community\/elders$/)
  await expect(elders).toHaveAttribute('aria-checked', 'true')
  await expect(elders).toHaveAttribute('style', /scale/)
  await page.screenshot({ path: testInfo.outputPath('jelly-island.png') })
})

test('mobile family preview scrolls its content', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.getByRole('button', { name: /体验演示/ }).click()

  const scroller = page.locator('[data-unified-scroller]')
  const family = page.locator('.unified-section-family .family-page')
  await expect(scroller).toBeVisible()
  const familyChip = page.getByTestId('global-island').locator('.jelly-radio__chip').nth(2)
  await familyChip.click()
  await expect(familyChip).toHaveAttribute('aria-checked', 'true')
  await expect.poll(() => scroller.evaluate(element => element.scrollTop / (element.scrollHeight - element.clientHeight))).toBeCloseTo(.5, 2)

  const dimensions = await family.evaluate(element => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight }))
  expect(dimensions.scrollHeight).toBeGreaterThan(dimensions.clientHeight)
  await page.mouse.move(190, 560)
  await page.mouse.wheel(0, 480)
  await expect.poll(() => family.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
})

test('JellyRadio filters the three lists by risk', async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/community/elders')
  const filter = page.getByRole('radiogroup', { name: '按风险等级筛选' })
  await expect(filter).toBeVisible()
  await expect(filter.getByRole('radio')).toHaveCount(4)
  const urgent = filter.getByRole('radio', { name: '紧急' })
  await urgent.click()
  await expect(urgent).toHaveAttribute('aria-checked', 'true')
  const archiveRows = page.locator('.data-section').first().locator('tbody tr')
  await expect(archiveRows.first()).toBeVisible()
  const rowCount = await archiveRows.count()
  for (let index = 0; index < rowCount; index += 1) {
    await expect(archiveRows.nth(index).getByText(/紧急/)).toBeVisible()
  }
  await page.screenshot({ path: testInfo.outputPath('jelly-risk-filter.png'), fullPage: true })
})

test('mobile layouts keep primary controls inside the viewport', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const [path, marker] of [
    ['/login', '我是老人'],
    ['/elder/home', '紧急求助'],
    ['/family/overview', '今日平安时间轴'],
    ['/community/alerts', '预警工单看板'],
  ]) {
    await page.goto(path)
    await expect(page.getByText(marker, { exact: false }).first()).toBeVisible()
    const hasPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasPageOverflow, `${path} should not overflow on mobile`).toBe(false)
  }
  await page.goto('/login')
  await page.getByRole('button', { name: /体验演示/ }).click()
  const island = page.getByRole('radiogroup', { name: '角色快捷入口' })
  await island.getByRole('radio', { name: '社区端' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.locator('.unified-section-community')).toBeInViewport()
  await page.goto('/family/overview')
  await page.screenshot({ path: testInfo.outputPath('family-mobile.png'), fullPage: true })
})

test('family registration signs in to the restricted family screen', async ({ page }) => {
  const username = `family_${Date.now()}`
  const phone = `138${String(Date.now()).slice(-8)}`
  await page.goto('/login')
  await page.getByRole('button', { name: /注册新账号/ }).click()
  await page.getByRole('radiogroup', { name: '注册角色' }).getByRole('radio', { name: /子女/ }).click()
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('邮箱').fill(`${username}@example.com`)
  await page.getByLabel('电话').fill(phone)
  await page.getByLabel('密码', { exact: true }).fill('family-pass-123')
  await page.getByLabel('确认密码').fill('family-pass-123')
  await page.getByRole('button', { name: /创建账号/ }).click()

  await expect(page).toHaveURL(/\/family\/overview$/)
  await expect(page.getByTestId('user-account-bar')).toContainText(username)
  await expect(page.getByTestId('global-island')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: /张桂芳/ })).toBeVisible()

  await page.goto('/community/dashboard')
  await expect(page).toHaveURL(/\/family\/overview$/)
  const forbiddenStatus = await page.evaluate(async () => (await fetch('/api/elders?preview=1')).status)
  expect(forbiddenStatus).toBe(403)

  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByRole('button', { name: /登录账号/ }).click()
  await page.getByRole('radiogroup', { name: '账号身份' }).getByRole('radio', { name: /普通用户/ }).click()
  await page.getByRole('button', { name: /继续/ }).click()
  const userRoles = page.getByRole('radiogroup', { name: '用户角色' })
  await expect(userRoles.getByRole('radio')).toHaveCount(4)
  await userRoles.getByRole('radio', { name: /子女/ }).click()
  await page.getByRole('button', { name: /继续/ }).click()
  await page.getByLabel('邮箱、电话或用户名').fill(`${username}@example.com`)
  await page.getByLabel('密码', { exact: true }).fill('family-pass-123')
  await page.getByRole('button', { name: /^登录/ }).click()
  await expect(page).toHaveURL(/\/family\/overview$/)
})

test('administrator login returns to the original home with full access', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: /登录账号/ }).click()
  await page.getByRole('radio', { name: /管理员/ }).click()
  await page.getByRole('button', { name: /继续/ }).click()
  await page.getByLabel(/邮箱、电话或用户名/).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill('admin123456')
  await page.getByRole('button', { name: /^登录/ }).click()

  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByTestId('global-island')).toBeVisible()
  const homeNavigation = page.getByRole('radiogroup', { name: '角色快捷入口' })
  await expect(homeNavigation.getByRole('radio')).toHaveCount(5)
  await homeNavigation.getByRole('radio', { name: '老人端' }).click()
  await expect(page.locator('.unified-section-elder')).toBeInViewport()
  await homeNavigation.getByRole('radio', { name: '社区端' }).click()
  await expect(page.locator('.unified-section-community .work-order-chart')).toBeVisible()

  await page.goto('/elder/sos')
  await expect(page.getByText('紧急求助', { exact: false }).first()).toBeVisible()
  await page.goto('/family/overview')
  await expect(page.getByText('今日平安时间轴')).toBeVisible()
  await page.goto('/volunteer/tasks')
  await expect(page.getByText('需要处理的任务')).toBeVisible()
})
