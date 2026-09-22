import type { Messages } from './index'

/**
 * chat —— AI 助手（components/ChatPanel.vue、components/ChatToolCard.vue、stores/chat.ts、api/chat.ts）。
 *
 * 边界：工具结果里的**数据**（股票名、行业名、推荐理由、策略名、AI 正文）来自后端，保持中文，
 * 不进词表；这里只收口 UI 外壳（按钮、占位符、卡片标签、兜底提示）。
 * requestFailed* 也被 api/index.ts 的通用 axios 客户端复用（对话错误气泡与 ElMessage 同源）。
 */

export const zh: Messages = {
  // 输入区
  placeholder: '输入问题，回车发送（Shift+回车换行）',
  clear: '清空',
  stop: '停止',
  send: '发送',
  // 未知工具的原始折叠面板
  args: '参数：',
  result: '结果：',
  // 欢迎语（空会话时由 ChatPanel 用当前语言现算，不入持久化）
  greeting: '你好！我是 EmoQunt AI 投资助手。我可以帮你查询行情、运行回测、分析舆情与推荐个股。试试问：',
  sampleQuote: '帮我看看 000001 最近行情',
  sampleBacktest: '运行 test 策略回测 000001',
  sampleSentiment: '今天哪些板块情绪最高？',
  sampleRecommend: '推荐几只股票',
  // 会话栏（多会话工作台：新建/切换/置顶/重命名/删除）
  sessions: {
    untitled: '新会话',
    newSession: '新会话',
    more: '更多操作',
    pin: '置顶',
    unpin: '取消置顶',
    rename: '重命名',
    delete: '删除',
    pinned: '已置顶',
    renameTitle: '重命名会话',
    renamePlaceholder: '输入新的会话标题',
    deleteConfirm: '确定删除会话「{title}」？删除后无法恢复。',
    deleted: '会话已删除',
  },
  // 空态启动卡片（按组分类的快捷提问，点击即发送）
  starter: {
    groups: {
      strategy: '股票策略',
      factor: 'A股因子',
      data: '数据查询',
    },
    cards: {
      ma: {
        label: '创建双均线代码策略',
        desc: '生成 SDK 源码并回测验证',
        q: '创建一个双均线代码策略并回测',
      },
      tuning: {
        label: '给绑定策略做参数调优',
        desc: '股票 000001，2024Q1，≤5 组网格',
        q: '给当前绑定策略做参数调优：股票 000001，区间 2024-01-01 到 2024-03-31，网格控制在 5 个组合以内',
      },
      factor: {
        label: '创建 20 日动量因子',
        desc: '生成因子并跑 IC/分层分析',
        q: '创建一个 20 日动量因子并分析',
      },
      quote: {
        label: '查个股行情',
        desc: '报价、区间涨跌与情绪卡片',
        q: '帮我看看 000001 最近行情',
      },
      sentiment: {
        label: '板块情绪排行',
        desc: '今日各行业情绪高低对比',
        q: '今天哪些板块情绪最高？',
      },
    },
  },
  // 对话状态 / 请求错误
  cancelled: '_(已取消)_',
  failed: '对话失败',
  requestFailed: '请求失败',
  requestFailedStatus: '请求失败 ({status})',
  // 工具结果卡片
  incomplete: '未完成',
  toolNoResult: '该工具调用未返回结果（已取消或服务异常）',
  signalBuy: '买入信号',
  signalSell: '卖出信号',
  signalHold: '观望',
  marketUs: '美股',
  marketCn: 'A股',
  indexName: '指数',
  periodHigh: '期间最高',
  periodLow: '期间最低',
  avgSentiment: '平均情绪',
  newsCount: '新闻 {n} 条',
  viewOnHome: '在首页查看主图',
  viewSentiment: '查看舆情分析',
  viewRecommend: '查看每日推荐',
  runBacktest: '去运行回测',
  stockSignal: '个股信号',
  sectorSentiment: '行业情绪',
  clickToViewOnHome: '点击在首页主图查看',
  // 工具卡标题（toolCards.ts 的 TOOL_LABELS 引用这些键，工具名本身是数据）
  toolQuote: '行情查询',
  toolIndex: '指数查询',
  toolSentiment: '舆情查询',
  toolRecommend: '每日推荐',
  toolBacktest: '策略回测',
  toolSignal: '个股信号',
  toolStrategies: '策略列表',
  toolStrategyCode: '策略代码',
  toolTuningCreate: '创建调优任务',
  toolTuningStatus: '调优进度',
  toolRun: '运行记录',
  toolRuns: '运行历史',
  toolFactors: '因子列表',
  toolFactorCreate: '创建因子',
  toolFactorAnalyze: '因子分析',
  // 绑定策略栏（ChatPanel 输入区上方；只存 id 不存名称）
  bindStrategy: '绑定策略',
  bindStrategyPlaceholder: '选择代码策略',
  // 策略代码卡片（get_strategy / create_strategy / update_strategy）
  strategyOpen: '打开策略库',
  strategyParams: '生效参数',
  strategyVersionSaved: '更新已保存，旧态已存为版本快照',
  // 调优任务卡片（create_tuning_task / get_tuning_status）
  tuneTotalCombos: '组合总数',
  tuneProgress: '{done}/{total} 组完成',
  tuneBest: '最优组合 #{n}',
  tuneBaseline: '基准',
  tuneColParams: '参数',
  tuneViewDetail: '查看调优详情',
  // 运行记录卡片（get_run；指标展示名复用 backtest.metric.*）
  runViewHistory: '查看运行历史',
  runTradeCount: '成交 {n} 笔',
  // 因子分析卡片（analyze_factor；IC 标签复用 factor.cards.*，分层表头复用 factor.table.*）
  factorOpenDetail: '打开因子详情',
  // 回测摘要卡片指标名（数值本身来自后端，保持原样）
  btTotalReturn: '总收益率',
  btAnnualReturn: '年化收益',
  btMaxDrawdown: '最大回撤',
  btSharpe: '夏普比率',
  btWinRate: '胜率',
  btProfitLossRatio: '盈亏比',
}

export const en: Messages = {
  // 输入区
  placeholder: 'Ask a question, press Enter to send (Shift+Enter for a new line)',
  clear: 'Clear',
  stop: 'Stop',
  send: 'Send',
  // 未知工具的原始折叠面板
  args: 'Args:',
  result: 'Result:',
  // 欢迎语（空会话时由 ChatPanel 用当前语言现算，不入持久化）
  greeting:
    "Hi! I'm the EmoQunt AI investment assistant. I can look up quotes, run backtests, analyze sentiment and pick stocks. Try asking:",
  sampleQuote: 'Show me how 000001 has been trading lately',
  sampleBacktest: 'Run the test strategy backtest on 000001',
  sampleSentiment: 'Which sectors have the highest sentiment today?',
  sampleRecommend: 'Recommend a few stocks',
  // 会话栏（多会话工作台：新建/切换/置顶/重命名/删除）
  sessions: {
    untitled: 'New chat',
    newSession: 'New chat',
    more: 'More actions',
    pin: 'Pin',
    unpin: 'Unpin',
    rename: 'Rename',
    delete: 'Delete',
    pinned: 'Pinned',
    renameTitle: 'Rename chat',
    renamePlaceholder: 'Enter a new chat title',
    deleteConfirm: 'Delete chat "{title}"? This cannot be undone.',
    deleted: 'Chat deleted',
  },
  // 空态启动卡片（按组分类的快捷提问，点击即发送）
  starter: {
    groups: {
      strategy: 'Stock strategies',
      factor: 'A-share factors',
      data: 'Data lookups',
    },
    cards: {
      ma: {
        label: 'Build a moving-average strategy',
        desc: 'Generate SDK source and backtest it',
        q: 'Create a dual moving average code strategy and backtest it',
      },
      tuning: {
        label: 'Tune the bound strategy',
        desc: 'Stock 000001, 2024Q1, grid of ≤5 combos',
        q: 'Tune the currently bound strategy: stock 000001, from 2024-01-01 to 2024-03-31, keep the grid under 5 combos',
      },
      factor: {
        label: 'Create a 20-day momentum factor',
        desc: 'Generate the factor, run IC and quantile analysis',
        q: 'Create a 20-day momentum factor and analyze it',
      },
      quote: {
        label: 'Look up a stock quote',
        desc: 'Price, range change and sentiment cards',
        q: 'Show me how 000001 has been trading lately',
      },
      sentiment: {
        label: 'Sector sentiment ranking',
        desc: 'Compare today’s sentiment across sectors',
        q: 'Which sectors have the highest sentiment today?',
      },
    },
  },
  // 对话状态 / 请求错误
  cancelled: '_(Cancelled)_',
  failed: 'Chat failed',
  requestFailed: 'Request failed',
  requestFailedStatus: 'Request failed ({status})',
  // 工具结果卡片
  incomplete: 'Incomplete',
  toolNoResult: 'This tool call returned no result (cancelled or service error)',
  signalBuy: 'Buy signal',
  signalSell: 'Sell signal',
  signalHold: 'Hold',
  marketUs: 'US',
  marketCn: 'A-share',
  indexName: 'Index',
  periodHigh: 'Period high',
  periodLow: 'Period low',
  avgSentiment: 'Avg. sentiment',
  newsCount: 'News: {n}',
  viewOnHome: 'View main chart on Home',
  viewSentiment: 'View sentiment analysis',
  viewRecommend: 'View daily picks',
  runBacktest: 'Run a backtest',
  stockSignal: 'Stock signal',
  sectorSentiment: 'Sector sentiment',
  clickToViewOnHome: 'Click to view on the Home chart',
  // 工具卡标题（toolCards.ts 的 TOOL_LABELS 引用这些键，工具名本身是数据）
  toolQuote: 'Stock Quote',
  toolIndex: 'Index Quote',
  toolSentiment: 'Sentiment Lookup',
  toolRecommend: 'Daily Picks',
  toolBacktest: 'Backtest',
  toolSignal: 'Stock Signal',
  toolStrategies: 'Strategies',
  toolStrategyCode: 'Strategy Code',
  toolTuningCreate: 'Tuning Task Created',
  toolTuningStatus: 'Tuning Progress',
  toolRun: 'Run Record',
  toolRuns: 'Run History',
  toolFactors: 'Factors',
  toolFactorCreate: 'Create Factor',
  toolFactorAnalyze: 'Factor Analysis',
  // 绑定策略栏（ChatPanel 输入区上方；只存 id 不存名称）
  bindStrategy: 'Bind strategy',
  bindStrategyPlaceholder: 'Select a code strategy',
  // 策略代码卡片（get_strategy / create_strategy / update_strategy）
  strategyOpen: 'Open strategy library',
  strategyParams: 'Effective params',
  strategyVersionSaved: 'Update saved; previous state stored as a version snapshot',
  // 调优任务卡片（create_tuning_task / get_tuning_status）
  tuneTotalCombos: 'Total combos',
  tuneProgress: '{done}/{total} combos done',
  tuneBest: 'Best combo #{n}',
  tuneBaseline: 'Baseline',
  tuneColParams: 'Params',
  tuneViewDetail: 'View tuning details',
  // 运行记录卡片（get_run；指标展示名复用 backtest.metric.*）
  runViewHistory: 'View run history',
  runTradeCount: '{n} trades',
  // 因子分析卡片（analyze_factor；IC 标签复用 factor.cards.*，分层表头复用 factor.table.*）
  factorOpenDetail: 'Open factor details',
  // 回测摘要卡片指标名（数值本身来自后端，保持原样）
  btTotalReturn: 'Total return',
  btAnnualReturn: 'Annual return',
  btMaxDrawdown: 'Max drawdown',
  btSharpe: 'Sharpe',
  btWinRate: 'Win rate',
  btProfitLossRatio: 'P/L ratio',
}
