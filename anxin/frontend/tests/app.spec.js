import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const accounts = [
  ['superadmin', '超级管理员', '系统管理员', '/admin/console', '系统管理'],
  ['elder', '老人', '张桂芳', '/elder/home', '今日平安'],
  ['family', '家属', '李伟', '/family/overview', '家人总览'],
  ['community', '社区', '王芳', '/community/alerts', '关爱响应'],
  ['volunteer', '志愿者', '赵敏', '/volunteer/tasks', '我的任务'],
]
async function submitDemo(page, role) {
  await page.getByRole('button', { name: '填入演示账号', exact: true }).click()
  await page.getByRole('button', { name: `登录${accounts.find(a => a[0] === role)[1]}工作台`, exact: true }).click()
}
async function login(page, role) {
  await page.goto(`/login?role=${role}`)
  await submitDemo(page, role)
  await expect(page).toHaveURL(accounts.find(a => a[0] === role)[3])
}

for (const [role, label, name, home, nav] of accounts) {
  test(`${role}: login, matching navigation, refresh and logout`, async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
    await page.getByRole('radio', { name: label, exact: true }).click()
    await expect(page.getByRole('radio', { name: label, exact: true })).toHaveAttribute('aria-checked', 'true')
    if (role === 'elder') await expect(page).toHaveURL(/\/login$/)
    else await expect(page).toHaveURL(new RegExp(`role=${role}`))
    await submitDemo(page, role)
    await expect(page).toHaveURL(home)
    const header = page.getByRole('navigation', { name: '主导航' })
    await expect(header.getByText(name, { exact: true })).toBeVisible()
    await expect(header.getByText(`${label}端 · 已登录`, { exact: true })).toBeVisible()
    await expect(header.getByRole('link', { name: nav, exact: true })).toHaveAttribute('aria-current', 'page')
    if (role !== 'community') await expect(header.getByRole('link', { name: '场景体验' })).toHaveCount(0)
    await page.reload()
    await expect(header.getByText(name, { exact: true })).toBeVisible()
    await header.getByRole('button', { name: '退出登录' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: '选择身份，登录工作台' })).toBeVisible()
    await expect(header.getByRole('button', { name: '退出登录' })).toHaveCount(0)
    expect((await (await page.request.get('/api/session')).json()).role).toBeNull()
    await page.goto(home)
    await expect(page).toHaveURL(/\/login\?/)
  })
}

test('wrong password shows clear feedback and protected links require correct identity', async ({ page }) => {
  await page.goto('/community/alerts')
  await expect(page).toHaveURL(/\/login\?role=community/)
  await page.getByRole('button', { name: '填入演示账号' }).click()
  await page.getByLabel('密码', { exact: true }).fill('incorrect')
  await page.getByRole('button', { name: '登录社区工作台' }).click()
  await expect(page.getByRole('alert')).toHaveText('账号或密码错误')
  await login(page, 'family')
  await page.goto('/community/alerts')
  await expect(page.getByRole('heading', { name: '请使用社区账号进入' })).toBeVisible()
  await expect(page.getByRole('navigation', { name: '主导航' }).getByText('李伟', { exact: true })).toBeVisible()
  const response = await page.request.get('/api/alerts')
  expect(response.status()).toBe(403)
  await page.getByRole('link', { name: '切换身份登录' }).click()
  await submitDemo(page, 'community')
  await expect(page).toHaveURL('/community/alerts')
})

test('community menu tracks URL and browser history', async ({ page }) => {
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  await login(page, 'community')
  const header = page.getByRole('navigation', { name: '主导航' })
  await header.getByRole('link', { name: '场景体验' }).click()
  await expect(page).toHaveURL('/demo/simulator')
  await expect(header.getByRole('link', { name: '场景体验' })).toHaveAttribute('aria-current', 'page')
  await page.goBack()
  await expect(header.getByRole('link', { name: '关爱响应' })).toHaveAttribute('aria-current', 'page')
  await header.getByRole('link', { name: '老人档案' }).click()
  await expect(header.getByRole('link', { name: '老人档案' })).toHaveAttribute('aria-current', 'page')
  expect(errors).toEqual([])
})

test('superadmin and community enter their management workspaces', async ({ page }) => {
  await login(page, 'superadmin')
  await expect(page.getByRole('heading', { name: '系统管理' })).toBeVisible()
  const tabs = page.getByRole('radiogroup', { name: '管理模块' })
  await tabs.getByRole('radio', { name: '角色权限' }).click()
  await expect(page.getByLabel('数据范围')).toBeVisible()
  await page.getByRole('link', { name: '个人中心', exact: true }).click()
  await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible()

  await login(page, 'community')
  const header = page.getByRole('navigation', { name: '主导航' })
  await header.getByRole('link', { name: '社区管理' }).click()
  await expect(page).toHaveURL('/community/manage')
  await expect(page.getByRole('heading', { name: '社区管理' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '账号', exact: true })).toBeVisible()
})

test('care workflow switches accounts explicitly and delivers family receipt', async ({ page }) => {
  await login(page, 'community')
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '场景体验' }).click()
  await page.getByRole('button', { name: '分析信号并生成判断' }).click()
  await page.getByRole('link', { name: '查看这条工单' }).click()
  await page.getByRole('button', { name: '安排人员跟进' }).click()
  await page.getByRole('button', { name: '确认提交', exact: true }).click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await page.getByRole('link', { name: '切换志愿者账号' }).click()
  await expect(page).toHaveURL(/\/login\?role=volunteer/)
  await submitDemo(page, 'volunteer')
  await expect(page).toHaveURL('/volunteer/tasks')
  await page.getByRole('article').filter({ hasText: '张桂芳' }).getByRole('button', { name: '到场打卡' }).click()
  await page.getByRole('button', { name: '确认提交', exact: true }).click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await page.getByRole('article').filter({ hasText: '张桂芳' }).getByRole('button', { name: '上传回执并归档' }).click()
  await page.getByRole('textbox', { name: '服务回执' }).fill('浏览器验证：已核实老人安全并联系家属。')
  await page.getByRole('button', { name: '确认提交', exact: true }).click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await login(page, 'family')
  await expect(page.locator('.care-notices').getByText(/浏览器验证：已核实老人安全并联系家属/).first()).toBeVisible()
})

test('jelly controls keep their active state and fit the mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.getByRole('radio', { name: '社区', exact: true }).click()
  await expect(page.getByRole('radio', { name: '社区', exact: true })).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('button', { name: '填入演示账号' }).click()
  await page.getByRole('button', { name: '登录社区工作台', exact: true }).click()
  await expect(page).toHaveURL('/community/alerts')

  const island = page.getByTestId('global-island')
  const header = page.getByRole('navigation', { name: '主导航' })
  await expect(island).toHaveCSS('border-radius', '999px')
  await expect(header.getByRole('link', { name: '关爱响应', exact: true })).toHaveAttribute('data-on', 'true')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)

  const filters = page.getByRole('radiogroup', { name: '筛选工单' })
  await filters.getByRole('radio', { name: '全部记录', exact: true }).click()
  await expect(filters.getByRole('radio', { name: '全部记录', exact: true })).toHaveAttribute('aria-checked', 'true')
  const cases = page.getByRole('radiogroup', { name: '工单列表' }).getByRole('radio')
  await expect(cases.first()).toBeVisible()
  if (await cases.count() > 1) {
    await cases.nth(1).click()
    await expect(cases.nth(1)).toHaveAttribute('aria-checked', 'true')
    await expect(page).toHaveURL(/id=\d+/)
  }

  await header.getByRole('link', { name: '场景体验', exact: true }).click()
  const scenarios = page.getByRole('radiogroup', { name: '选择模拟场景' })
  await scenarios.getByRole('radio', { name: /正常生活/ }).click()
  await expect(scenarios.getByRole('radio', { name: /正常生活/ })).toHaveAttribute('aria-checked', 'true')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
})

test('desktop and mobile login and role navigation stay within viewport', async ({ page }) => {
  mkdirSync(resolve('../preview'), { recursive: true })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '选择身份，登录工作台' })).toBeVisible()
  await page.screenshot({ path: resolve('../preview/login-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: '填入演示账号' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.screenshot({ path: resolve('../preview/login-mobile.png'), fullPage: true })
  await login(page, 'community')
  const header = page.getByRole('navigation', { name: '主导航' })
  await expect(header.getByRole('link', { name: '关爱响应' })).toBeVisible()
  await expect(header.getByRole('button', { name: '退出登录' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.screenshot({ path: resolve('../preview/navigation-mobile.png'), fullPage: false })
})

test('community manages scoped notification templates and device history', async ({ page }) => {
  await login(page, 'community')
  const simulated = await page.request.post('/api/simulator/trigger', { data: { scenario: 'normal' } })
  expect(simulated.status()).toBe(200)

  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '社区管理' }).click()
  const tabs = page.getByRole('radiogroup', { name: '管理模块' })
  await tabs.getByRole('radio', { name: '设备', exact: true }).click()
  await page.getByRole('button', { name: '查看 DEV-001-01 的设备读数趋势' }).click()
  const history = page.getByRole('dialog')
  await expect(history).toContainText(/\d+ 条读数/)
  await history.getByRole('button', { name: '关闭' }).click()

  await tabs.getByRole('radio', { name: '通知模板', exact: true }).click()
  await page.getByLabel('模板名称').fill('访问进展模板')
  await page.getByLabel('发送对象').selectOption('family')
  await page.getByLabel('消息类型').selectOption('service')
  await page.getByLabel('消息标题').fill('本周探访安排')
  await page.getByLabel('消息内容').fill('志愿者将于周五上午到访。')
  await page.getByRole('button', { name: '创建', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: '访问进展模板' })).toBeVisible()

  await tabs.getByRole('radio', { name: '消息', exact: true }).click()
  await page.getByLabel('套用通知模板').selectOption({ label: '访问进展模板' })
  await expect(page.getByLabel('消息标题')).toHaveValue('本周探访安排')
  await expect(page.getByLabel('消息内容')).toHaveValue('志愿者将于周五上午到访。')
})

test('superadmin can configure periodic backup interval', async ({ page }) => {
  await login(page, 'superadmin')
  const tabs = page.getByRole('radiogroup', { name: '管理模块' })
  await tabs.getByRole('radio', { name: '备份恢复', exact: true }).click()
  const interval = page.getByLabel('间隔（小时）')
  await expect(interval).toHaveValue('24')
  await interval.fill('48')
  await page.getByRole('button', { name: '保存间隔' }).click()
  await expect(interval).toHaveValue('48')
})
