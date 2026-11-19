# 安芯 · 独居老人安全守护与社区关爱平台

中国大学生计算机设计大赛 Web 应用与开发赛道演示项目。

当前版本采用 **React + Vite + Flask + SQLite**：React 负责全部页面与交互，Flask 仅提供 JSON API、会话和生产静态资源入口。

## 快速启动

仓库已包含构建后的 React 文件，首次运行只需：

```powershell
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000`。

首次运行会自动生成 `anxin.db` 演示数据库。需要重置演示数据时，停止服务、删除 `anxin.db`，然后重新运行。

## 前端开发

先启动 Flask API：

```powershell
python app.py
```

另开终端启动 Vite：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。Vite 会把 `/api` 和 `/static` 代理到 Flask。

完成修改后生成生产文件：

```powershell
cd frontend
npm run build
```

构建结果输出到 `static/react/`，由 Flask 直接发布。

## 项目结构

```text
anxin/
├─ app.py                    # Flask API、会话与 React SPA 入口
├─ db.py                     # SQLite 建表和演示数据
├─ anxin.db                  # 本地演示数据库（不提交）
├─ frontend/
│  ├─ src/
│  │  ├─ components/        # 导航、图表、对话框、长按等通用组件
│  │  ├─ pages/             # 9 个 React 业务页面
│  │  ├─ App.jsx            # 路由、会话与全局通知
│  │  └─ react.css          # React 页面补充样式
│  ├─ tests/                # Playwright 桌面/移动端验收
│  └─ vite.config.js
├─ static/
│  ├─ css/                  # 既有设计令牌与视觉样式
│  └─ react/                # Vite 生产构建结果
└─ tests/                   # Flask + SQLite 集成测试
```

## 页面路由

| 路由 | 页面 |
|---|---|
| `/login` | 四角色演示登录 |
| `/` | 登录后的统一首页与五端演示入口 |
| `/elder/home` | 老人端今日平安、语音与长按求助 |
| `/elder/sos` | SOS 长按、倒计时、通知与医疗卡 |
| `/family/overview` | 家属总览、活动时间轴与异常提醒 |
| `/community/dashboard` | 社区安全驾驶舱 |
| `/community/elders` | 老人档案、需求、服务资源三个清单 |
| `/community/alerts` | 预警工单状态看板 |
| `/volunteer/tasks` | 志愿者到场、回执和归档 |
| `/demo/simulator` | IoT 异常场景模拟器 |

## 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/auth/login` | 管理员或普通用户登录 |
| POST | `/api/auth/register` | 注册普通用户账号并绑定角色 |
| POST | `/api/auth/logout` | 清除登录会话 |
| GET/POST/DELETE | `/api/session` | 查询、设置、清除演示角色 |
| GET | `/api/elder/home` | 老人首页数据 |
| POST | `/api/checkin` | 今日平安打卡 |
| POST | `/api/sos` | 触发 SOS 预警 |
| GET | `/api/family/overview` | 家属端聚合数据 |
| GET | `/api/dashboard` | 驾驶舱聚合数据 |
| GET | `/api/elders` | 三个清单与个人基线摘要 |
| GET | `/api/alerts` | 全部预警工单 |
| POST | `/api/alerts/{id}/dispatch` | 派单 |
| POST | `/api/alerts/{id}/process` | 开始处置 |
| POST | `/api/alerts/{id}/close` | 提交处置回执并转待回访 |
| POST | `/api/alerts/{id}/follow-up` | 回访后归档 |
| GET | `/api/volunteer/tasks` | 志愿者任务 |
| POST | `/api/simulator/trigger` | 注入模拟异常场景 |

## 核心闭环

- `sensor_readings` 记录每日活动窗口，`IsolationForest` 使用个人最近最多 30 个窗口评分；个人样本不足 7 个时回退到社区演示基线。
- 异常等级由异常分位分级，跌倒置信度达到 0.85 且静止超过 10 分钟时强制升级为紧急；告警保留分数、基线范围和可解释原因。
- 异常预警自动生成探访需求，并匹配独立维护的服务资源清单；三个清单分别是老人档案、需求和服务资源，关联结果可追溯。
- 工单状态为“待核实 → 已派单 → 处置中 → 待回访 → 已归档”，每次流转写入 `work_order_logs`，回访记录单独写入 `follow_up_records`。
- 登录区分管理员和普通用户。普通用户注册时绑定老人、子女、社区或志愿者角色，并只访问对应端；管理员登录后进入统一首页，可使用原有五端入口及完整页面和接口权限。未登录演示预览使用 `preview=1`。

SQLite 中的个人资料及 IoT 历史均为合成演示数据，模型输出不可用于真实医疗或紧急救援决策。管理员初始演示账号为 `admin`；部署时请通过 `ANXIN_ADMIN_PASSWORD` 配置密码，并设置随机的 `ANXIN_SECRET_KEY`。

## 验证

```powershell
# Flask API 与临时数据库集成测试
python -m unittest discover -s tests -v

# React 静态检查与生产构建
cd frontend
npm run lint
npm run build

# Edge 桌面/移动端浏览器验收
npm run test:e2e
```

Playwright 验收覆盖全部 React 路由、控制台错误、驾驶舱画布、角色登录以及移动端横向溢出。
