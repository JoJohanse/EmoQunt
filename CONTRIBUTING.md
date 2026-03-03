# 贡献指南 (Contributing Guide)

感谢您有兴趣为 Qdt_test 项目做出贡献！本文档提供了有关如何参与项目开发的指导。

## 开发环境设置

1. 克隆项目仓库：
   ```bash
   git clone <repository-url>
   cd Qdt_test
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   - 在 `.env` 文件中设置 `ZHI_TU_API_TOKEN` 以使用智兔API

## 项目结构

```
Qdt_test/
├── src/                    # 源代码目录
│   ├── Stock.py           # 股票数据获取
│   ├── get_hs300.py       # 沪深300成分股获取
│   ├── Strategy/          # 策略框架
│   │   ├── Strategy.py    # 策略基类和管理器
│   │   └── SentimentMAStrategy.py  # 情绪策略
│   ├── factor/            # 因子相关模块
│   │   ├── sentiment_analyzer.py   # 情绪分析
│   │   ├── math_calculate.py       # 技术指标
│   │   ├── factor_analysis.py      # 因子分析
│   │   └── factor_preprocess.py    # 因子预处理
│   ├── performance.py     # 绩效评估
│   ├── visualization.py   # 可视化
│   ├── backtest_runner.py # 回测运行器
│   ├── risk_management.py # 风险管理
│   └── utils/             # 工具模块
│       └── logger.py      # 日志系统
├── config/                # 配置文件目录
│   ├── config.yaml        # 项目配置文件
│   └── config_loader.py   # 配置加载器
├── nes_data/              # 新闻数据目录
├── stock_data/            # 股票数据目录
└── test/                  # 测试文件目录
```

## 代码规范

### Python 代码规范

- 遏循 [PEP 8](https://pep8.org/) 代码风格
- 使用 [Google 风格的 docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- 函数命名使用 `snake_case`
- 类命名使用 `PascalCase`
- 常量使用 `UPPER_CASE`

### 示例代码结构

```python
def example_function(param1: str, param2: int) -> bool:
    """
    示例函数说明。

    Args:
        param1: 参数1的说明
        param2: 参数2的说明

    Returns:
        返回值的说明
    """
    # 函数实现
    return True
```

## 测试

在提交代码之前，请确保：

1. 所有现有测试通过
2. 为新功能添加适当的测试
3. 运行测试套件：
   ```bash
   python -m pytest test/
   ```

## 提交拉取请求 (Pull Request)

1. Fork 项目仓库
2. 从 `main` 分支创建新分支：
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. 进行更改并提交：
   ```bash
   git add .
   git commit -m "Add your descriptive commit message"
   ```
4. 推送分支：
   ```bash
   git push origin feature/your-feature-name
   ```
5. 创建拉取请求

### PR 描述模板

请在 PR 描述中包含以下信息：

- 更改的内容
- 为什么需要这些更改
- 如何测试这些更改
- 相关的 issue 编号（如果有）

## 代码审查过程

1. 所有 PR 都需要至少一位维护者的批准
2. 代码应遵循项目规范
3. 应包含适当的测试
4. 文档应相应更新

## 报告问题

当报告问题时，请包含：

- 问题的详细描述
- 重现步骤
- 预期行为
- 实际行为
- 环境信息（操作系统、Python 版本等）

## 联系方式

如有疑问，请联系项目维护者或在 GitHub 上开 issue。

---

感谢您的贡献！