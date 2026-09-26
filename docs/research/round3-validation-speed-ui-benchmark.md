# Round3 对标研究：行情获取速度 · 策略有效性检验 · UI 可视化

日期：2026-09-26。前三轮研究（homepage-ui-benchmark v1-v4、kline-chart-benchmark）聚焦首页与 K 线形态；本轮按目标要求补三条新线：**行情获取速度、策略有效性检验、UI 交互与可视化**。结论已落为 Round3 实现（见 §4）。

## 一、策略有效性检验（对标 freqtrade / vectorbt / 学术口径）

现状缺口（代码摸底结论）：调优是**纯 in-sample 网格 argmax**（`src/services/tuning.py`，63 组同一区间挑最优，零防过拟合设计）；回测指标缺 Sortino；月度收益热力图只有 matplotlib 路径未进 JSON API；交易明细只有 K 线 markPoint 无表格。

| 参照 | 做法 | 本轮采纳 |
|---|---|---|
| [freqtrade backtesting 文档](https://www.freqtrade.io/en/stable/backtesting/) | 官方立场：回测极易被扭曲，推荐 **in-sample 优化 + 未触碰的 out-of-sample 时段验证**；性能在 OOS 崩塌即过拟合信号 | ✅ 调优任务默认按 70/30 切 IS/OOS：网格在 IS 区间跑，IS 排名 Top-K + 基准在 OOS 区间复跑，最终排名按 OOS 指标；OOS 相对 IS 退化时前端出过拟合警示 |
| [vectorbt 优化功能](https://vectorbt.dev/) | `rolling_split` 做 walk-forward；参数网格结果用热力图呈现参数敏感性 | ✅（部分）前端调优详情补参数敏感性可视化（1 参数=散点/折线，2 参数=热力图）；完整 walk-forward 多折列为后续 |
| PBO / Deflated Sharpe（Bailey & López de Prado） | CSCV 组合对称交叉验证算过拟合概率；DSR 按试验次数缩水夏普 | ❌ 学术口径实现成本高；本轮用「OOS/IS 退化幅度」做实用化替代警示，walk-forward+PBO 列为远期 |
| FreqUI 回测页布局 | 指标面板含 **Sortino**；交易明细表（开平时间/时长/盈亏%）是标配；月度收益矩阵（month×year 热力图）来自生态报表工具 | ✅ Sortino 进指标链；月度收益进 JSON + ECharts 热力图；交易明细表（前端 FIFO 配对 fills 成 round-trip，含持仓天数/单笔盈亏） |

## 二、行情获取速度（对标 akshare 生态与自建缓存实践）

现状缺口（代码摸底结论）：①主取数链与 akshare 调用**无超时**，`market._call_with_timeout` 因 executor `shutdown(wait=True)` 对真挂死的调用实际失效；②`get_market_overview` 串行 N+1（5 指数 + ≤10 自选逐个取数）；③**PG 部分覆盖即命中且永不补新**（`db.get_cached_range` PG 分支无覆盖校验、`get_latest_date` 是死代码）——数据停在旧日期时 SWR 后台刷新也救不回，DB 不可用时退化为每次全窗口重下；④warmup 串行。

| 参照 | 做法 | 本轮采纳 |
|---|---|---|
| [akshare stock_zh_a_spot_em](https://akshare.akfamily.xyz/data/stock/stock.html) | 一次请求拉全 A 股 5800+ 只实时快照，社区惯用「全量快照+本地过滤自选池」 | ❌（本轮）overview 已有 SWR 分量缓存，收益大头在并行化；批量快照接口列为后续 |
| 反爬/限流现实（akshare/efinance 均为爬虫型源，可能单源长挂） | 免费源无 SLA，单源挂死不能拖垮整链 | ✅ `fetch_runner.run_source_chain` 增加每源硬超时（daemon 线程 + join(timeout)，超时=该源失败进下一源）；`market._call_with_timeout` 改同款非阻塞实现 |
| 本项目 daily_recommend 已有 8 线程并行取数先例 | `ThreadPoolExecutor` 并行逐只 | ✅ `get_market_overview` 指数+自选+宽度/板块并发化；warmup 默认自选并行预热 |
| 增量更新通行做法（"最新日期已是今天/昨天则跳网"） | 缓存命中后检查尾部覆盖，只向网络补缺口 | ✅ `KlineProvider.fetch_daily` 增量补拉：命中后若头部/尾部有缺口，仅向网络补拉缺口窗口并合并回填（10 分钟节流防重复出网），修复"PG 部分覆盖永远返回旧数据"的正确性缺陷 |

## 三、UI 交互与可视化（对标 FreqUI / TradingView 式回测报告）

现状缺口（代码摸底结论）：全站表格零排序；回测三图独立缩放无联动；图表 tooltip/文字色硬编码白底（暗色主题下刺眼）；ECharts 232KB gz 与首屏同载；调优参数组合只是一格字符串。

| 参照 | 做法 | 本轮采纳 |
|---|---|---|
| FreqUI 回测报告 | 交易明细表可排序、月度收益矩阵 | ✅ BacktestView 交易明细表 + 月度热力图（HeatmapChart 已按需注册，接根线即用） |
| ECharts 原生能力 | `axisPointer.link` + `dataZoom` group 多图联动 | ✅ 回测净值/回撤/日收益三图联动 |
| 通用暗色规范 | 图表颜色跟随主题，不硬编码 | ✅ 新增 `lib/chartTheme.ts`（读 uiStore.theme 输出 tooltip/文字/轴线色），替换硬编码点位；主题切换响应式重渲染 |
| 按需加载 | 图表库首屏外懒加载 | ✅ `components/LazyChart.vue`（defineAsyncComponent 包 vue-echarts），首屏直减 ~232KB gz |
| Element Plus 按需引入（unplugin） | 主 chunk 483KB gz 有望砍到 ~150KB | ❌ 本轮不做（改动面大、影响全部组件注册），列为后续 |
| 表格交互 | 全站 `el-table` 加 `sortable` | ✅ 调优组合表/运行历史/交易明细等低成本加 |

## 四、Round3 落地清单（实现对照）

后端：
1. `src/data/fetch_runner.py` — 每源硬超时（`QDT_SOURCE_TIMEOUT`，默认 30s，超时记 source_health 失败）。
2. `src/services/market.py` — `_call_with_timeout` 非阻塞化；`get_market_overview` 并发化。
3. `src/services/warmup.py` — 默认自选并行预热。
4. `src/data/provider.py` — DB 命中后头部/尾部增量补拉 + 合并回填（10 分钟节流）。
5. `src/backtest/backtest_manager.py` — Sortino（索提诺比率）进 PerformanceAnalyzer 与 `_format_metrics_json`；`run_backtest_json` payload 增 `monthly_returns`。
6. `src/services/tuning.py` + `src/store/db.py` — 样本外验证：`oos_ratio`（默认 0.3，0 关闭）、IS/OOS 双阶段执行、OOS 复跑 Top-K、`oos_metrics_json` 落库、过拟合退化指标。

前端：
7. BacktestView — 交易明细表（FIFO 配对 + 持仓天数 + 单笔盈亏）、月度收益热力图、Sortino 卡片、三图 axisPointer 联动。
8. TuningDetailView — IS/OOS 双列指标、OOS 阶段进度、过拟合警示条、参数敏感性视图、表格 sortable。
9. `lib/chartTheme.ts` 暗色适配 + `LazyChart.vue` ECharts 懒加载。
10. 词表：backtest/tuning 域新增键，zh/en 双树对称。

## 五、后续候选（本轮不做）

- 全市场批量快照接口（`stock_zh_a_spot_em`）替代自选逐只 kline。
- 完整 walk-forward 多折 + PBO / Deflated Sharpe。
- Element Plus 按需引入（unplugin-vue-components）。
- 移动端断点与抽屉导航；HomeView 拆分；相关性矩阵。

## 参考来源

- [freqtrade backtesting](https://www.freqtrade.io/en/stable/backtesting/) · [freqtrade advanced backtesting](https://www.freqtrade.io/en/stable/advanced-backtesting/)
- [vectorbt](https://vectorbt.dev/)（rolling_split / 参数热力图）
- [AKShare 文档](https://akshare.akfamily.xyz/)（stock_zh_a_spot_em 全市场快照等）
- Bailey & López de Prado, *The Deflated Sharpe Ratio*（2014）与 CSCV/PBO 系列论文（学术口径，未实现，列为远期）
