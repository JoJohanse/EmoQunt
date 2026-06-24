# EmoQunt 前端（Vue3 SPA）

现代 Vue3 + Vite + TypeScript 单页应用，替代原有的 Jinja2 + Bootstrap 服务端渲染前端。

## 技术栈

- **框架**：Vue 3.5（`<script setup>` 组合式 API）
- **构建**：Vite 6 + vue-tsc 类型检查
- **路由**：Vue Router 4（history 模式）
- **状态**：Pinia
- **UI**：Element Plus 2.9 + 图标
- **HTTP**：axios（统一 `/api` 前缀）
- **图表**：ECharts 5 + vue-echarts（按需引入，动态可交互）

## 目录结构

```
frontend/
├── index.html              # SPA 入口
├── package.json
├── vite.config.ts          # Vite 配置 + /api 代理
├── tsconfig.json / *.app / *.node
├── public/
│   └── favicon.svg
└── src/
    ├── main.ts             # 应用入口（注册 Element Plus、Pinia、Router）
    ├── App.vue             # 根组件（Layout 包裹 RouterView）
    ├── assets/main.css     # 全局样式 + CSS 变量设计令牌
    ├── layouts/AppLayout.vue   # 顶部导航 + 页脚布局
    ├── router/index.ts     # 路由定义（5 个页面）
    ├── api/
    │   ├── index.ts        # axios 实例 + 各 API 模块
    │   └── types.ts        # 后端返回类型定义
    ├── composables/
    │   └── useECharts.ts   # ECharts 按需注册
    └── views/
        ├── HomeView.vue            # 首页
        ├── BacktestView.vue        # 回测（ECharts 动态图表）
        ├── StrategiesView.vue      # 策略列表
        ├── SentimentView.vue       # 舆情分析
        └── DailyRecommendView.vue  # 每日推荐
```

## 开发

```bash
cd frontend
npm install
npm run dev      # 启动 Vite 开发服务器（http://localhost:5173）
```

开发模式下，`/api` 请求经 Vite 代理转发到 FastAPI（`127.0.0.1:8000`）。需同时运行后端：

```bash
python web_app.py
```

## 构建

```bash
npm run build    # 类型检查 + 生产构建，产物输出到 frontend/dist/
```

构建产物由 FastAPI 静态托管：
- `/assets/*` → `frontend/dist/assets/`
- `/spa/*` → `frontend/dist/index.html`（history 路由回退）

生产访问：http://localhost:8000/spa/

## 动态图表

回测页（`BacktestView.vue`）的收益曲线、回撤曲线、日收益率均为 ECharts 动态渲染：
- 支持鼠标缩放、数据钻取（tooltip）
- 支持区间刷选（dataZoom）
- 支持导出图片（toolbox）
- 数据来自 `POST /api/backtest/run` 返回的 JSON 时序数据（非 matplotlib 静态 PNG）

## API 契约

前端依赖的 JSON API（均由 `web_app.py` 提供）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategies/list` | GET | 策略列表（数组） |
| `/api/strategies/detail/{name}` | GET | 策略详情 |
| `/api/strategies/templates` | GET | 策略模板 |
| `/api/strategies/create_new` | POST | 创建策略 |
| `/api/strategies/create_from_template` | POST | 从模板创建 |
| `/api/strategies/{name}` | PUT/DELETE | 更新/删除 |
| `/api/backtest/run` | POST | 运行回测（JSON 时序） |
| `/api/sentiment/data` | GET | 舆情数据 |
| `/api/daily-recommend` | GET | 每日推荐 |
| `/api/daily-recommend/refresh` | GET | 刷新推荐 |
