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
  // 欢迎语（仅在没有本地持久化消息时出现，由 store 初始化时用当前语言生成）
  greeting: '你好！我是 EmoQunt AI 投资助手。我可以帮你查询行情、运行回测、分析舆情与推荐个股。试试问：',
  sampleQuote: '帮我看看 000001 最近行情',
  sampleBacktest: '运行 test 策略回测 000001',
  sampleSentiment: '今天哪些板块情绪最高？',
  sampleRecommend: '推荐几只股票',
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
  // 欢迎语（仅在没有本地持久化消息时出现，由 store 初始化时用当前语言生成）
  greeting:
    "Hi! I'm the EmoQunt AI investment assistant. I can look up quotes, run backtests, analyze sentiment and pick stocks. Try asking:",
  sampleQuote: 'Show me how 000001 has been trading lately',
  sampleBacktest: 'Run the test strategy backtest on 000001',
  sampleSentiment: 'Which sectors have the highest sentiment today?',
  sampleRecommend: 'Recommend a few stocks',
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
  // 回测摘要卡片指标名（数值本身来自后端，保持原样）
  btTotalReturn: 'Total return',
  btAnnualReturn: 'Annual return',
  btMaxDrawdown: 'Max drawdown',
  btSharpe: 'Sharpe',
  btWinRate: 'Win rate',
  btProfitLossRatio: 'P/L ratio',
}
