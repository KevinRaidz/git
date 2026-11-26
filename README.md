# 安芯关爱平台

面向独居老人关怀与社区服务协作的本地演示应用，采用 React、Vite、Flask 和 SQLite。React 提供角色工作台与管理界面，Flask 负责登录会话、权限校验、业务 API 和静态资源。

## 角色与权限

- 超级管理员：账号与角色、权限配置、系统设置、操作日志、数据导入导出和备份。
- 社区管理员：管理本社区老人、家属关系、设备、预警工单、志愿者和服务记录。
- 志愿者：查看分配给自己的任务，提交到场、回执和归档信息。
- 家属：查看绑定老人的基本信息、预警进展、服务记录和站内消息。
- 老人：使用报平安、紧急求助和联系人等适老化页面。

权限由后端接口执行，包含角色权限和数据范围校验；社区数据按社区隔离，志愿者任务仅对被分配者开放。账号密码使用哈希存储。

## 功能

- 登录、退出、会话保持、个人资料和密码管理。
- 按角色展示工作台、菜单与快捷入口。
- 老人档案、家属绑定、设备与历史读数、分级预警及工单时间线。
- 探访服务、志愿者派单、到场记录、服务回执和家属反馈。
- 站内消息、公告与通知模板。
- 角色权限、数据范围、字典、平台配置及审计日志。
- CSV 数据导入导出、手动与定期数据库备份、备份恢复。
- 胶囊形全局导航与 JellyRadio 动效切换。

## 本地运行

在仓库根目录执行：

```powershell
python -m pip install -r anxin/requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000/login`。首次运行会初始化本地 SQLite 演示数据库和演示账号；登录页可查看体验账号。演示数据仅用于本地体验。

## Render 全栈部署

应用由 Flask 同时提供 React 构建文件和 `/api` 接口。部署到 Render Web Service，不要将它作为纯静态 Cloudflare Pages 项目。

在 Render 连接 GitHub 仓库并创建 Web Service，填写：

| 设置 | 值 |
|---|---|
| Root Directory | `anxin` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --workers 1 --worker-class gthread --threads 8 --bind 0.0.0.0:$PORT wsgi:app` |

为 Web Service 添加持久化磁盘，Mount Path 设为 `/var/data`。在 Environment 中设置以下变量；密码和密钥应使用独立的随机值，不要提交到 Git：

| 变量 | 示例值/要求 |
|---|---|
| `ANXIN_ENV` | `production` |
| `ANXIN_SECRET_KEY` | 至少 32 个字符的随机密钥 |
| `ANXIN_ADMIN_PASSWORD` | 至少 10 个字符；首次初始化时用于 `admin_demo` |
| `ANXIN_DEMO_PASSWORD` | 至少 10 个字符；首次初始化时用于其他演示账号 |
| `ANXIN_DB_PATH` | `/var/data/anxin.db` |
| `ANXIN_BACKUP_DIR` | `/var/data/backups` |

Render 会提供 `PORT`，无需手动设置。首次部署会在持久化磁盘中初始化 SQLite 数据库并生成演示数据。账号密码变量只用于新建账号；已有数据库中的密码不会在每次启动时被覆盖。完成部署后先登录并修改账号密码，再绑定自有域名。Cloudflare 可用于 DNS 和域名管理，无需再创建 Pages 前端部署。

当前数据库仍是 SQLite，适合演示和小规模验证；正式承载真实健康或联系信息前，应评估 PostgreSQL、访问控制、数据备份恢复、隐私和运维要求，并清理演示数据。

## 前端开发

先在仓库根目录启动 Flask，然后另开终端：

```powershell
cd anxin/frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。Vite 会将 API 请求代理到本机 Flask。生产构建命令为：

```powershell
npm run build
```

构建产物输出到 `anxin/static/react/`，由 Flask 提供服务。

## 路由

| 路由 | 页面 |
|---|---|
| `/login` | 登录与身份入口 |
| `/admin/console` | 超级管理员工作台与系统管理 |
| `/community/dashboard` | 社区工作台 |
| `/community/elders` | 老人档案与服务清单 |
| `/community/alerts` | 预警和工单处理 |
| `/volunteer/tasks` | 志愿任务与服务回执 |
| `/family/overview` | 家属关怀总览 |
| `/elder/home` | 老人平安页 |
| `/elder/sos` | 老人紧急求助 |
| `/profile` | 个人中心 |

## 测试

```powershell
cd anxin
python -m unittest discover -s tests -v
cd frontend
npm run lint
npm run build
npm run test:e2e
```

Playwright 使用隔离的临时 SQLite 数据库，不会改动本地演示数据库。

## 项目结构

```text
app.py                         # 仓库根启动入口
anxin/
  app.py                       # Flask 应用与 API
  wsgi.py                      # Gunicorn 生产启动入口
  access_control.py            # 角色、接口和数据范围校验
  admin_api.py                 # 管理、审计、导入导出与备份 API
  accounts.py                  # 账号、角色与默认演示数据
  care.py                      # 预警、工单流转与提醒
  db.py                        # SQLite 数据访问和初始化
  frontend/src/                # React 页面与组件
  static/react/                # 前端生产构建文件
  tests/                        # Flask 与权限测试
```

## 演示边界

本项目用于本地协作和功能演示，不连接真实传感器、短信、电话或救援系统。上线前需配置独立密钥、修改演示账号密码，并完成安全、隐私、备份恢复和真实业务流程审查。
