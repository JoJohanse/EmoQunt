# EmoQunt 量化系统

基于舆情分析的智能量化投资策略回测平台。

## 功能特点

- **策略回测**: 支持多种量化策略的回测分析
- **舆情分析**: 基于实时热点舆论数据生成交易信号
- **每日推荐**: 智能推荐潜力股票
- **策略管理**: 创建和管理自定义量化策略

## 系统架构

```
EmoQunt/
├── config/                 # 配置文件
├── src/                   # 源代码
│   ├── Strategy/          # 策略模块
│   ├── analysis/         # 分析模块
│   ├── backtest/         # 回测模块
│   ├── data/             # 数据管理
│   ├── factor/           # 因子模块（情绪、技术、市值等）
│   ├── risk/             # 风险管理
│   ├── utils/            # 工具函数
│   └── visualization.py  # 可视化
├── stock_data/            # 股票数据
├── web/                  # Web应用
│   ├── templates/        # HTML模板
│   └── app.py           # Web应用
└── web_app.py           # 主入口
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

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python web_app.py
```

访问 http://localhost:8000

## 页面功能

### 1. 首页 (/)
系统概览，展示主要功能入口

### 2. 策略回测 (/backtest)
- 选择股票和策略
- 设置回测参数
- 查看回测绩效

### 3. 策略列表 (/strategies)
- 查看所有可用策略
- 创建新策略
- 编辑/删除自定义策略

### 4. 舆情分析 (/sentiment)
- 展示当天热门新闻
- 显示各板块舆情得分
- 情绪趋势可视化

### 5. 每日推荐 (/daily_recommend)
- 基于舆情分析推荐股票
- 显示推荐理由和评分

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategies` | GET | 获取策略列表 |
| `/api/strategies/detail/{name}` | GET | 获取策略详情 |
| `/api/strategies` | POST | 创建新策略 |
| `/api/strategies/{name}` | PUT | 更新策略 |
| `/api/strategies/{name}` | DELETE | 删除策略 |
| `/api/sentiment` | GET | 获取舆情分析结果 |

## 技术栈

- **后端**: FastAPI
- **前端**: Bootstrap 5 + Jinja2
- **数据**: baostock (A股数据)
- **分析**: pandas, numpy

## 配置

配置文件位于 `config/config.yaml`

## 注意事项

- 确保股票数据文件已正确配置
- 舆情分析需要有效的API Key
