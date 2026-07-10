# EmoQunt 量化系统

> [English](README_EN.md) | 中文

基于舆情分析的智能量化投资策略回测平台。融合行业情绪因子、A股真实交易成本与沪深300基准，提供从策略构建、回测到绩效分析的一站式 Web 体验。

## 功能特点

### 回测引擎
- **A股真实交易成本**：佣金（双边，含最低 5 元）、印花税（仅卖出 0.05%）、过户费（双边 0.001%）与滑点建模
- **基准与风险调整收益**：自动获取沪深300指数，计算 Alpha / Beta / 信息比率，并在图表中绘制基准对比曲线
- **情绪过滤策略**：策略的均线交叉信号可由历史情绪快照过滤（"截至当日最近快照"，避免未来函数）
- **交易级胜率**：胜率按已平仓交易（tradeanalyzer.won/lost）计算，而非错误的"盈利交易日占比"
- **绩效分析器**：总/年化收益率、夏普比率、最大回撤、卡玛比率、VaR/CVaR、下行标准差等

### Web 前端
- **统一设计系统**：基于 `base.html` 基础模板 + `app.css` 设计令牌（CSS 变量），全站一致的导航栏、页脚与紫渐变主题
- **8 个页面**：首页、策略回测（表单+结果）、策略管理、舆情分析（含个股入口）、每日推荐、错误页
- **统一技术栈**：Bootstrap 5.3 + Font Awesome 6 + Jinja2 模板继承
- **响应式**：移动端汉堡菜单与卡片自适应

### 其它
- **AI 投资助手**：基于 LangGraph 的 ReAct agent，通过自然语言对话调用行情/回测/舆情/推荐/策略工具，SSE 流式输出、Markdown 渲染、工具调用可见（全局对话面板）
- **舆情分析**：基于 TrendRadar 实时热点舆论数据生成板块情绪得分与个股交易信号
- **每日推荐**：融合情绪与多因子模型（涨跌幅/量能/舆情/技术形态）智能推荐
- **策略管理**：基于 JSON 配置动态创建策略，支持模板参数编辑
- **测试覆盖**：pytest 覆盖成本模型、参数解析、绩效指标、Alpha/Beta、情绪面板、agent 工具

## 系统架构

```
EmoQunt/
├── config/                 # 配置文件
│   ├── config.yaml         # 主配置文件
│   └── config_loader.py    # 配置加载器
├── nes_data/               # 舆情数据与快照
│   └── sentiment_results/  # 历史情绪快照 ({YYYYMMDD}.json)
├── src/                    # 源代码
│   ├── Strategy/           # 策略模块
│   │   ├── Strategy.py     # 策略基类 + 动态策略工厂 + 情绪过滤
│   │   └── strategy_manager.py
│   ├── analysis/           # 因子分析
│   ├── backtest/           # 回测模块
│   │   └── backtest_manager.py  # AShareCommInfo / PerformanceAnalyzer / BacktestRunner
│   ├── data/               # 数据管理
│   │   └── data_manager.py      # Stock / get_index_data / 情绪快照加载
│   ├── factor/             # 因子模块
│   │   ├── sentiment.py    # 情绪因子（LLM 评分）
│   │   ├── technical.py    # 技术因子
│   │   ├── market.py       # 市场因子
│   │   └── daily_recommend.py   # 每日推荐
│   ├── risk/               # 风险管理（仓位/止损/VaR）
│   ├── utils/              # 工具函数
│   └── visualization.py    # 可视化
├── test/                   # 测试
│   └── test_backtest.py    # 回测模块单元测试
├── web/                    # Web 应用
│   ├── templates/          # Jinja2 模板（extends base.html）
│   │   ├── base.html       # 基础模板（导航栏/页脚/head）
│   │   ├── index.html      # 首页
│   │   ├── backtest_form.html / backtest_result.html
│   │   ├── strategies.html
│   │   ├── sentiment_analysis.html / sentiment_result.html
│   │   ├── daily_recommend.html
│   │   └── error.html
│   └── static/
│       ├── css/app.css     # 全站设计系统
│       └── favicon.svg
├── web_app.py              # 主入口（FastAPI）
├── requirements.txt        # 依赖文件
└── README.md
```

## 页面预览

### 首页
![首页](web/templates/首页.png)

### 策略管理
![策略管理](web/templates/回测策略管理.png)

### 回测结果
![回测结果](web/templates/回测结果.png)

### 每日推荐
![每日推荐](web/templates/每日推荐.png)

### 舆情分析
![舆情分析](web/templates/舆情分析.png)

## 快速开始

### 环境要求
- Python 3.11+（推荐 conda 环境）
- 网络访问（akshare 行情数据、TrendRadar 舆情、LLM API）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置
1. 复制并编辑环境变量（如 LLM API Key 等）
2. 编辑 `config/config.yaml` 调整回测/风险参数

### 启动服务

```bash
python web_app.py
```

访问 http://localhost:8000

### 运行测试

```bash
pytest test/test_backtest.py -v
```

## 页面功能

| 路由 | 功能 |
|------|------|
| `/` | 首页，功能入口与系统特性 |
| `/backtest` | 策略回测表单（支持 `?strategy_name=` 预选） |
| `/run_backtest` | 回测结果（绩效指标卡 + 收益/回撤/仪表板图表） |
| `/strategies` | 策略列表，创建/编辑/删除自定义策略 |
| `/sentiment` | 舆情分析（热门新闻 + 板块得分 + 个股分析入口） |
| `/analyze_sentiment` | 个股情绪结果（信号、得分、情绪分布图） |
| `/daily_recommend` | 每日推荐（Top3 板块 + 排名股票表） |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategies` | GET | 获取策略列表 |
| `/api/strategies/detail/{name}` | GET | 获取策略详情 |
| `/api/strategies/create_new` | POST | 自定义创建策略 |
| `/api/strategies/create_from_template` | POST | 从模板创建策略 |
| `/api/strategies/templates` | GET | 获取策略模板 |
| `/api/strategies/{name}` | PUT | 更新策略 |
| `/api/strategies/{name}` | DELETE | 删除策略 |
| `/api/sentiment` | GET | 获取舆情分析结果 |

## 回测引擎要点

### A股交易成本
回测默认启用 `AShareCommInfo` 成本模型，相对 backtrader 默认的对称佣金更贴近真实：
- 佣金：双边，默认万三，单笔不低于 5 元
- 印花税：**仅卖出** 0.05%
- 过户费：双边 0.001%
- 滑点：可配置（默认 0.05%）

### 基准与风险调整收益
- 自动获取沪深300（000300）日线作为基准
- 计算 Alpha / Beta（协方差法）、信息比率
- 收益曲线与仪表板中绘制基准对比

### 情绪过滤
- 扫描 `nes_data/sentiment_results/*.json` 历史快照，构建"快照日期 × 行业"情绪面板
- 通过 `StockSectorMapper` 定位回测股票的行业
- 回测中某日仅使用"截至该日最近的历史快照"，**避免未来函数**
- `use_sentiment_filter=True` 时，金叉买入需行业情绪 ≥ −threshold，死叉卖出需 ≤ threshold

## 技术栈

- **后端**：FastAPI + Uvicorn + Jinja2
- **前端**：Bootstrap 5.3 + Font Awesome 6（共享 `base.html` + `app.css` 设计系统）
- **数据**：akshare（A股行情与指数）
- **回测**：backtrader + 自定义 A股成本模型
- **分析**：pandas, numpy, scipy, scikit-learn
- **可视化**：matplotlib, seaborn, plotly
- **情绪**：OpenAI 兼容 LLM（SiliconFlow/Qwen）+ LangChain
- **测试**：pytest

## 配置

配置文件位于 `config/config.yaml`，包含：
- `backtest`：初始资金、佣金费率、滑点开关与费率
- `risk_management`：最大日亏、最大回撤、杠杆、持仓/行业暴露限制
- `data` / `strategy` / `factor` 等其它模块参数

## 策略管理

用户可通过 Web 界面或直接编辑 `src/Strategy/user_strategies/strategies.json` 创建自定义策略，基于 `sentiment_ma`（情绪均线）模板配置参数。

## 注意事项

- 回测首次获取行情/指数数据需联网（结果会缓存到 `stock_data/`）
- 舆情分析需要有效的 LLM API Key（在 `config/config.yaml` 或环境变量配置）
- 首次运行时系统会自动生成 `logs/`、`output/`、`nes_data/` 等目录
- 缓存文件位于 `nes_data/`，可根据需要手动清理
- 回测结果仅供参考，不构成投资建议

## 贡献指南

请参考 [CONTRIBUTING.md](CONTRIBUTING.md) 文件。

## 许可证

本项目采用 [MIT](LICENSE) 许可证。
