# EmoQunt - 综合舆情分析的量化交易策略回测系统

一个基于情绪因子和传统技术因子的量化交易策略回测系统，支持因子分析、风险管理、绩效评估等功能，并提供直观的Web界面。

## 项目概述
一个成熟的自动化套利系统通常包含四个模块：

Scanner 市场扫描器
Monitor 行情监控器
Executor 执行引擎
Settler 结算引擎
它们分别解决四个问题：

哪里有机会
机会是否真实
如何无风险执行
如何回收资金

本项目是一个完整的量化交易策略研究和回测平台，主要特点包括：

- **多因子模型**：结合情绪因子和传统技术因子
- **完整回测系统**：支持策略回测和绩效评估
- **风险管理**：包含仓位控制、止损止盈、VaR计算等功能
- **因子分析**：支持因子有效性检验、预处理、中性化等
- **可视化**：提供丰富的图表展示功能
- **Web界面**：直观的Web界面，方便用户操作和查看结果

## 核心功能模块

### 1. 数据获取模块 (`src/data/`)
- **data_manager.py**: 支持 A 股股票数据获取（日线、分钟级）
- 支持复权处理（前复权、后复权、不复权）
- 本地数据缓存机制
- akshare 数据源
- 沪深300成分股获取

### 2. 策略框架 (`src/Strategy/`)
- **StrategyBase**: 策略基类
- **SimpleMAStrategy**: 简单移动平均线策略
- **SentimentMAStrategy**: 情绪因子结合移动平均线策略
- 策略管理器和交易记录管理

### 3. 因子计算 (`src/factor/`)
- **sentiment.py**: 情绪分析和情绪因子计算
- **market.py**: 市场数据和估值指标获取
- **technical.py**: 技术指标计算 (MA, RSI, MACD, ATR, K值等)
- **sector.py**: 股票行业映射和沪深300成分股检查
- **trendradar.py**: 趋势雷达数据获取和新闻分析

### 4. 分析模块 (`src/analysis/`)
- **factor_analyzer.py**: 因子分析和预处理
- 因子有效性检验（IC值、ICIR）
- 因子预处理（去极值、标准化、中性化）
- 因子分层回测

### 5. 回测模块 (`src/backtest/`)
- **backtest_manager.py**: 完整回测框架和绩效评估
- 组合管理功能
- 调仓逻辑（周度/月度）
- 基准对比功能
- 绩效评估（年化收益率、夏普比率、最大回撤等）

### 6. 风险模块 (`src/risk/`)
- **risk_manager.py**: 风险管理
- 仓位控制
- 止损止盈机制
- VaR计算
- 黑名单机制
- 压力测试

### 7. 可视化 (`src/visualization.py`)
- 收益曲线、回撤曲线
- 收益分布直方图
- 月度收益热力图
- 综合绩效仪表板

### 8. Web界面 (`web_app.py`)
- 基于FastAPI的Web服务
- 直观的策略回测界面
- 实时图表展示（使用Matplotlib生成）
- 详细的绩效报告

### 9. 配置管理 (`config/`)
- **config.yaml**: 项目配置文件，包含数据、策略、回测、风险等各项配置
- **config_loader.py**: 配置加载器，支持YAML配置文件和环境变量混合加载

### 10. 日志系统 (`src/utils/logger.py`)
- 统一日志管理
- 多级日志支持
- 日志轮转功能
- 异常处理装饰器

## 安装依赖

```bash
pip install -r requirements.txt
```

## Web界面使用指南

### 启动Web服务器

```bash
python web_app.py
```

服务器将在 `http://127.0.0.1:8000` 启动。

### Web界面功能

1. **首页**：展示系统功能和特性
2. **策略回测**：运行策略回测并查看结果
3. **策略列表**：查看所有可用策略及其参数

### 运行回测步骤

1. 访问 `http://127.0.0.1:8000`
2. 点击 "策略回测" 进入回测页面
3. 填写回测参数：
   - **策略选择**：从下拉菜单选择要测试的策略
   - **初始资金**：设置回测的初始资金（默认100000）
   - **开始日期**：选择回测开始日期
   - **结束日期**：选择回测结束日期
   - **佣金率**：设置交易佣金率（默认0.001）
   - **股票代码**：输入要测试的股票代码（默认000001平安银行）
4. 点击 "运行回测" 按钮
5. 查看回测结果页面，包括：
   - 绩效指标（总收益率、年化收益率、夏普比率等）
   - 收益曲线图表
   - 回撤曲线图表
   - 综合绩效仪表板

### 图表生成

系统使用 Matplotlib 库在本地生成图表，并保存到 `output` 文件夹中。图表包括：

- **收益曲线**：展示策略的累计收益变化
- **回撤曲线**：展示策略的最大回撤情况
- **绩效仪表板**：综合展示策略的各项指标

### 查看历史回测结果

所有回测生成的图表都保存在 `output` 目录中，按策略名称和时间戳组织：

```
output/
└── {strategy_name}_{stock_code}/
    └── {timestamp}/
        ├── equity_curve_{strategy_name}_{stock_code}_{timestamp}.png
        ├── drawdown_curve_{strategy_name}_{stock_code}_{timestamp}.png
        └── performance_dashboard_{strategy_name}_{stock_code}_{timestamp}.png
```

## 命令行使用示例

### 1. 基础策略回测

```python
from src.backtest import BacktestRunner

# 创建回测运行器
runner = BacktestRunner()

# 设置初始资金
runner.set_initial_capital(100000.0)

# 设置交易佣金
runner.set_commission(0.001)

# 添加分析器
runner.add_analyzers()

# 添加策略
runner.add_strategy('simple_ma', short_period=10, long_period=30)

# 运行回测
results = runner.run_backtest()

# 分析绩效
report = runner.analyze_performance()
```

### 2. 因子分析

```python
import pandas as pd
import numpy as np
from src.analysis import FactorAnalyzer

# 创建模拟数据
dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
stocks = [f'STOCK_{i:03d}' for i in range(50)]

factor_data = pd.DataFrame(
    np.random.randn(len(dates), len(stocks)),
    index=dates,
    columns=stocks
)

returns_data = pd.DataFrame(
    np.random.randn(len(dates), len(stocks)) * 0.01,
    index=dates,
    columns=stocks
)

# 因子分析
analyzer = FactorAnalyzer(factor_data, returns_data)
ic_series = analyzer.calculate_ic()
ic_stats = analyzer.calculate_ic_stats()

print(f"IC均值: {ic_stats['ic_mean']:.4f}")
print(f"IC IR: {ic_stats['ic_ir']:.4f}")
```

### 3. 风险管理

```python
from src.risk import RiskManager

# 创建风险管理器
risk_manager = RiskManager(initial_capital=100000)
risk_manager.set_risk_limits(max_daily_loss=0.02, max_drawdown=0.1)

# 更新投资组合价值
risk_manager.update_portfolio_value(95000)

# 检查交易限制
allow_trading, restrictions = risk_manager.check_trading_restrictions(95000)
```

## 补充说明
### TrendRadar 部署与集成

#### 什么是 TrendRadar

TrendRadar 是一个实时热点舆论获取工具，用于收集和分析财经新闻，为量化策略提供情绪因子数据。

#### 使用 Docker 部署 TrendRadar

1. **准备工作**
   - 确保已安装 Docker 和 Docker Compose
   - 进入 TrendRadar 目录

   ```bash
   cd nes_data/trendradar
   ```

2. **配置环境变量**
   - 复制 `.env` 文件模板
   ```bash
   cp docker/.env.example .env
   ```
   - 编辑 `.env` 文件，根据需要配置相关参数

3. **启动容器**
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

4. **验证部署**
   - 查看容器状态
   ```bash
   docker ps
   ```
   - 查看日志
   ```bash
   docker logs trend-radar
   ```

5. **配置爬取频率**
   - 在 `.env` 文件中修改 `CRON_SCHEDULE` 参数，例如：
   ```
   CRON_SCHEDULE=*/15 * * * *  # 每15分钟爬取一次
   ```

#### 与当前项目配合使用

1. **数据路径配置**
   - TrendRadar 的输出数据会自动保存在 `nes_data/trendradar/output` 目录
   - 当前项目已配置为从该目录读取数据

2. **使用舆情分析功能**
   - 启动 Web 服务器
   ```bash
   python web_app.py
   ```
   - 访问 `http://127.0.0.1:8000/sentiment`
   - 选择策略和股票代码（仅支持沪深300成分股）
   - 点击 "开始分析" 按钮

3. **查看分析结果**
   - 系统会显示：
     - 情绪得分和调整后得分
     - 基于策略情绪权重的交易信号
     - 情绪分布图表
     - 最新舆情新闻

#### 常见问题与解决方案

1. **TrendRadar 没有生成数据**
   - 检查容器是否运行：`docker ps`
   - 查看容器日志：`docker logs trend-radar`
   - 确保配置了正确的爬取频率

2. **舆情分析显示 "没有获取到新闻数据"**
   - 检查 `nes_data/trendradar/output` 目录是否存在
   - 检查是否有日期文件夹和 txt 文件
   - 等待 TrendRadar 完成第一次爬取

3. **股票代码不支持**
   - 仅支持沪深300成分股
   - 查看 `stock_data/沪深300/沪深300成分股列表.csv` 确认股票是否在列表中

4. **Docker 部署失败**
   - 检查 Docker 是否正常运行
   - 检查网络连接
   - 查看详细错误信息：`docker-compose -f docker/docker-compose.yml up`

## 项目结构

```
Qdt_test/
├── src/                    # 源代码目录
│   ├── data/               # 数据模块
│   │   ├── __init__.py
│   │   └── data_manager.py  # 股票数据获取和沪深300成分股获取
│   ├── analysis/           # 分析模块
│   │   ├── __init__.py
│   │   └── factor_analyzer.py # 因子分析和预处理
│   ├── backtest/            # 回测模块
│   │   ├── __init__.py
│   │   └── backtest_manager.py # 回测运行器和绩效评估
│   ├── risk/                # 风险模块
│   │   ├── __init__.py
│   │   └── risk_manager.py  # 风险管理
│   ├── factor/              # 因子模块
│   │   ├── __init__.py
│   │   ├── sentiment.py     # 情绪分析和情绪因子计算
│   │   ├── market.py        # 市场数据和估值指标获取
│   │   ├── technical.py     # 技术指标计算
│   │   ├── sector.py        # 股票行业映射和沪深300成分股检查
│   │   └── trendradar.py    # 趋势雷达数据获取和新闻分析
│   ├── Strategy/            # 策略框架
│   │   ├── __init__.py
│   │   ├── Strategy.py      # 策略基类和管理器
│   │   └── SentimentMAStrategy.py  # 情绪策略
│   ├── visualization.py     # 可视化
│   └── utils/               # 工具模块
│       ├── __init__.py
│       └── logger.py        # 日志系统
├── config/                  # 配置文件目录
│   ├── config.yaml          # 项目配置文件
│   └── config_loader.py     # 配置加载器
├── web/                     # Web界面目录
│   ├── templates/           # HTML模板
│       ├── index.html       # 首页
│       ├── backtest_form.html # 回测表单
│       └── backtest_result.html # 回测结果
├── output/                  # 图表输出目录
├── nes_data/                # 新闻数据目录
├── stock_data/              # 股票数据目录
└── test/                    # 测试文件目录
```
### stock_data目录下压缩包解压后目录结构

```
stock_data/
├── 沪深300/
│   ├── 沪深300成分股列表.csv
├── zh_a/
│   ├── 000001/
│   │   ├── hfq/
│   │   │   ├── daily/
│   │   │   │   ├── 000001_hfq_daily_20200101_20241231.csv
│   │   │   │   └── ...
│   │   │   └── ...
│   │   └── ...
│   └── ...

已包含沪深300成分股近五年的（2020~2024）的股票数据，每个股票一个文件夹，文件夹名为股票代码
```

## 环境配置

1. 安装依赖包
2. 配置 `.env` 文件中的智兔API密钥
3. 确保网络连接以获取实时数据

## 开发计划

- [x] 项目结构规范化
- [x] 基础策略框架
- [x] 情绪因子策略
- [x] 绩效评估系统
- [x] 回测系统
- [x] 因子分析模块
- [x] 风险管理系统
- [x] 配置管理系统
- [x] 日志系统
- [x] Web界面
- [ ] 数据库支持
- [x] 完整文档

## 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进项目。

## 许可证

[MIT License](LICENSE)
