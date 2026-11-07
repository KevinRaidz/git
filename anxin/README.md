# 安芯 · 独居老人 AI 安全守护与社区关爱平台（第一版 Demo）

中国大学生计算机设计大赛 · Web 应用与开发赛道

## 一、在 PyCharm 中运行（3 步）

1. PyCharm → File → Open → 选择 `anxin` 文件夹（本目录）
2. 打开 PyCharm 底部 Terminal（终端），执行：
   ```
   pip install -r requirements.txt
   ```
3. 右键 `app.py` → Run 'app'，浏览器访问 **http://127.0.0.1:5000**

> 首次运行自动生成 `anxin.db`（SQLite，含 24 位老人、6 条预警工单等演示数据）。
> 想重置数据：停掉服务 → 删除 `anxin.db` → 重新运行。

## 二、目录结构与"在哪改什么"

```
anxin/
├─ app.py               # 全部路由与 API（页面逻辑都在这）
├─ db.py                # 建表 + 演示数据种子（改数据去 seed() 函数）
├─ anxin.db             # SQLite 数据库（自动生成，可删）
├─ requirements.txt     # 依赖：只有 flask
├─ templates/           # 页面模板（HTML + Jinja2 + 少量 JS）
│   ├─ base.html        # 公共骨架 + 顶部导航
│   ├─ login.html       # 四角色演示登录
│   ├─ elder_home.html  # 老人端·今日平安（大字版）
│   ├─ elder_sos.html   # 老人端·SOS 三阶段流程
│   ├─ family_overview.html  # 子女端·总览（时间轴+活动图表）
│   ├─ dashboard.html   # 社区端·安全驾驶舱（深色大屏）
│   ├─ elders.html      # 社区端·老人档案+三个清单
│   ├─ alerts.html      # 社区端·预警工单看板
│   ├─ volunteer.html   # 志愿者端·任务
│   └─ simulator.html   # 演示模拟器（答辩总开关）
└─ static/css/
    ├─ common.css       # Design Token + 公共组件（改主题色看这里）
    ├─ elder.css        # 老人端大字样式
    └─ dashboard.css    # 驾驶舱深色样式
```

## 三、常用修改指南

| 想改什么 | 去哪改 |
|---|---|
| 主题色 / 字号 | `static/css/common.css` 顶部 `:root` 变量 |
| 老人端文案/按钮 | `templates/elder_home.html` |
| 驾驶舱图表 | `templates/dashboard.html` 底部 `<script>`（ECharts 配置） |
| 演示数据（老人名单、工单） | `db.py` 的 `seed()` 函数 |
| 新增页面 | `templates/` 加模板 + `app.py` 加路由 |

## 四、API 一览（供后续接 Vue/小程序前端复用）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/checkin | 老人打卡 |
| POST | /api/sos | 触发 SOS（生成红色预警） |
| GET  | /api/dashboard | 驾驶舱聚合数据（前端 5s 轮询） |
| GET  | /api/alerts | 全部预警工单 |
| POST | /api/alerts/{id}/dispatch | 派单 |
| POST | /api/alerts/{id}/process | 开始处置 |
| POST | /api/alerts/{id}/close | 归档（含误报学习） |
| POST | /api/simulator/trigger | 模拟器注入场景 fall / no_water / door_stuck |

## 五、第一版已实现 / 待开发

**已实现：**
- 四角色登录与页面骨架（设计规格书全部 10 个页面）
- 老人端：打卡（语音播报）、SOS 长按→倒计时→急救卡全流程
- 子女端：状态卡、今日时间轴、一周活动量图表（ECharts）、异常提醒
- 社区端：深色驾驶舱（风险环形/地图点位/趋势/工单状态/跑马灯，5s 轮询自动刷新）、三个清单、预警工单看板（核实→派单→处置→归档 全流程可点）
- 志愿者端：接单、GPS 到场打卡、回执归档
- 模拟器：三个场景一键注入，联动全部端

**待开发（按规格书排期推进）：**
- [ ] 真实地图（高德 JS API，需申请免费 key，替换 dashboard 的示意地图）
- [ ] SSE 替换轮询（`/api/stream/alerts`）
- [ ] 活跃度指数定时任务（z-score 算法已在规格书 8.1，当前为静态阈值）
- [ ] 用户登录鉴权（当前为演示免密）、audit_log 审计
- [ ] 报表导出 Excel、大模型语音陪伴接入

## 六、注意事项

- ECharts 通过 CDN 加载，首次打开需联网；离线演示请把 echarts.min.js 下载到 `static/js/` 并替换两处 `<script src>`。
- 数据为模拟生成，页面已标注，答辩时可主动说明（诚实标注是加分项）。
