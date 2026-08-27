# K线/行情图表展示 — 技术调研

> 调研日期：2026-08-27。目标：优化 K 线等行情数据图表的展示方式，为仪表盘 v3 之后的下一轮迭代提供选型与落地依据。
> 调研范围：主流 K 线图表库一手资料（官方文档 / 官方 GitHub README / 官方示例）、主流行情平台的 K 线交互范式、可视化最佳实践、以及本项目既有实现的盘点。

## 一、调研对象

| 方向 | 候选 | 官方入口 | 与 EmoQunt 的关联 |
|---|---|---|---|
| 通用可视化 | [Apache ECharts](https://echarts.apache.org/) | https://echarts.apache.org/ · https://github.com/apache/echarts | 项目已采用（`frontend/src/composables/useECharts.ts` 按需注册），dashboard 热力图/指数卡片/回测曲线均基于它 |
| 金融专用 | [KLineChart](https://www.klinecharts.com/) | https://www.klinecharts.com/ · https://github.com/klinecharts/KLineChart | 垂直 K 线库，内置 30+ 指标、分时/多周期、移动端手势；评估是否替换/并存 |
| 金融专用 | [TradingView lightweight-charts](https://tradingview.github.io/lightweight-charts/) | https://tradingview.github.io/lightweight-charts/ · https://github.com/tradingview/lightweight-charts | 极简高性能金融图库，社区生态大；评估轻量场景 |
| 商业套件 | [Highcharts Stock](https://www.highcharts.com/products/stock/) | https://www.highcharts.com/products/stock/ · https://www.highcharts.com/demo/stock/candlestick-and-volume | 40+ 指标、Navigator 预览、RangeSelector；评估商业成本是否值得 |

> 其它库（Chart.js、ApexCharts、Recharts、AntV G2）未列入：前三者在金融场景缺少蜡烛图/指标/多窗格原生能力，G2 定位偏统计图表，增量价值不大。

---

## 二、主流 K 线图表库对比

### 1. 对比总表

| 维度 | ECharts 5.6 / 6.0 | KLineChart 10.0.x | lightweight-charts 5.2 | Highcharts Stock 12.x |
|---|---|---|---|---|
| **定位** | 通用图表，金融只是其中一种 `series-candlestick` | 垂直金融图表（只做 K 线及衍生） | 垂直金融图表（极简高性能） | 垂直金融图表（商业套件） |
| **体积（gzip 实测区间）** | 全量 ~320KB；按需 + `CanvasRenderer` 后约 110–150KB（取决于注册组件数） | 零依赖，gzip ~40KB [^kline-size] | v5  Base ~35–45KB，含多窗格后亦 <60KB [^lw-size] | Core + Stock ~180–220KB，不含指标按需加载 |
| **无网络依赖本地引入** | ✅ `npm install echarts` ESM 按需引入；`vue-echarts` 7.x 封装；离线可打包 | ✅ `npm install klinecharts` 或 `cdn.jsdelivr.net` UMD；`init(id)` / `dispose(id)` | ✅ `npm install lightweight-charts` ESM + IIFE Standalone；离线可用 | ✅ `npm install highcharts`，但商业项目需在 Highsoft 商店购买授权后才可发布 |
| **许可证** | Apache-2.0 | Apache-2.0 | Apache-2.0（需在页面保留 TradingView 署名/链接，`attributionLogo` 选项可满足） [^lw-license] | 商业授权；仅个人/学校/非营利可申请非商业免费授权，SaaS/内网收费项目必须付费 [^hs-license] |
| **A 股红涨绿跌** | `series-candlestick.itemStyle.color / color0 / borderColor*` 任意配置；项目已按 `market` 区分 `upColor/downColor` | `styles.candle.bar.upColor / downColor` 全局样式表可配置，支持红涨绿跌 | `CandlestickSeries` 的 `upColor/downColor` + `wickUpColor/wickDownColor` / `borderUpColor/borderDownColor` | `series.upColor / color` + `lineColor` |
| **指标支持** | 蜡烛自带仅 OHLC，需自行叠加 `line`/`bar` 计算 MA/BOLL，或用 `custom` 系列画带状；社区有 `echarts-custom-series` 可复用 | 内置 30+：MA/EMA/SMA/BBI/VOL/MACD/BOLL/KDJ/RSI/BIAS/BRAR/CCI/DMI/CR/PSY/DMA/TRIX/OBV/VR/WR/MTM/EMV/SAR/AO/ROC/PVT/AVP [^kline-indicator]；蜡烛兼容的叠加类为 BBI/BOLL/EMA/MA/SAR/SMA | 无内置指标，需自行计算后用 `LineSeries`/`HistogramSeries`/`CustomSeries` 叠加；官方强调“通过 indicator 方法 + plugin 扩展” [^lw-indicator] | 内置 40+：SMA/EMA/MACD/CCI/RSI/随机指标/布林带/PSAR/一目均衡等 [^hs-indicator] |
| **缩放平移** | `dataZoom` (`inside` 滚轮/拖动 + `slider` 滑块) 双联动 + `toolbox.dataZoom`；`inside` 支持 `zoomOnMouseWheel / moveOnMouseDrag / moveOnMouseMove` | 原生：滚轮缩放、拖动平移、双指缩放、十字光标；`setZoom` / `setVisibleRange` | 原生：滚轮缩放、拖拽平移、双指缩放、`kineticScroll` 惯性；`timeScale.fitContent()` / `setVisibleRange` | `navigator` 预览 + `rangeSelector` + `scrollbar` + `ordinal` 轴断点（跳过停牌） |
| **实时推送** | `setOption({ series: [{ data }] })` 增量；大数据用 `appendData`（仅部分系列） | `updateData(bar)` / `setDataLoader` 流式 | `series.update(bar)` 追加单个点，无需重绘全量，性能最好 | `series.addPoint([t, o,h,l,c], true, shift)` |
| **文档质量** | 官方手册 + `option` 全量 API + 200+ 示例（含 Basic/Large-Scale/Brush/Matrix Stock [^echarts-ex]) | VitePress 文档（指南/指标/覆盖物/样式/FAQ），中英双语，示例覆盖 React/Vue/Angular [^kline-docs] | Docusaurus 5.2 文档（Getting Started / Tutorials / API Reference 含 `CandlestickSeries/HistogramSeries/PaneApi`） [^lw-docs] | 官方 Demo + API Reference + Stock 专项文档，最全但示例偏商业数据 |
| **维护活跃度（2025–2026）** | 极活跃：Apache 顶级项目，6.0 于 2025–2026 区间发布，新增「交易图增强、Matrix 坐标系、Broken Axis」等 12 项 [^echarts-v6]，GitHub >60k star，近 30 天仍有提交 | 活跃：GitHub 4.1k star / 992 fork，npm `klinecharts@10.0.2` 于 2026-08-22 发布（距今 5 天），主分支 1,739 commits | 活跃：GitHub 13k+ star，v5 于 2024–2025 重构 panes + plugin 体系，5.2 为当前稳定版，2025–2026 仍在发布 | 活跃：Highsoft 商业团队持续发布，但大版本需付费升级 |

[^kline-size]: KLineChart README："Only 40k under gzip compression. Zero dependencies." — https://github.com/klinecharts/KLineChart
[^lw-size]: lightweight-charts v5 发布博文："bringing the base bundle size down to 35kB"（v5 相比 v4 再降 16%）— https://www.tradingview.com/blog/en/tradingview-lightweight-charts-version-5-50837/ ；官网首页："At just 45 kilobytes" — https://www.tradingview.com/lightweight-charts/
[^lw-license]: lightweight-charts README License 节："Licensed under the Apache License, Version 2.0 ... This license requires specifying TradingView as the product creator. ... You can use the `attributionLogo` chart option" — https://github.com/tradingview/lightweight-charts
[^hs-license]: Highcharts 官网："Buy a license. You can download and try out all Highcharts products for free. Once your project/product is ready for launch, purchase a commercial license." / 非商业授权需单独申请 — https://www.highcharts.com/demo/stock/candlestick-and-volume ；https://shop.highcharts.com/
[^kline-indicator]: KLineChart 官方《技术指标》列出 28+ 内置及默认参数，并说明 `BBI/BOLL/EMA/MA/SAR/SMA` 可叠加在蜡烛窗格 — https://klinecharts.com/en-US/guide/indicator
[^lw-indicator]: lightweight-charts 官方通过二次计算 + `addSeries(LineSeries/HistogramSeries)` 或 `CustomSeries` 实现指标，无内置 MA/MACD — https://tradingview.github.io/lightweight-charts/docs/tutorials/how-to/add-indicators
[^hs-indicator]: Highcharts Stock Features："40+ Tech indicators Including SMA, MACD, CCI, RSI, Stochastic, Bollinger Bands, Pivot Points, PSAR, and Ichimoku Kinko Hyo." — https://www.highcharts.com/products/stock/
[^kline-docs]: KLineChart 快速上手与指南 — https://klinecharts.com/guide/quick-start.html ；https://klinecharts.com/guide/indicator
[^lw-docs]: lightweight-charts API Reference（`CandlestickSeries / HistogramSeries / IChartApi / IPaneApi / createChart`）— https://tradingview.github.io/lightweight-charts/docs/api
[^echarts-ex]: ECharts 官方示例分类 `Candlestick` 含 Basic / OHLC / ShangHai Index / Large Scale / Brush / Matrix Stock — https://echarts.apache.org/examples/en/index.html
[^echarts-v6]: ECharts 6.0 特性总览（12 项升级，含 Enhanced Stock Trading Charts / Matrix / Broken Axis / Beeswarm）— https://echarts.apache.org/handbook/en/basics/release-note/v6-feature/

### 2. 分库细读

#### ECharts（本项目已采用）

- **优势**：一库覆盖全站（仪表盘看板、行业热力图 `treemap`、回测净值/回撤/日收益、K 线/成交量），`vue-echarts@7` + 按需 `use([...])` 已把打包体积压到可接受区间；`dataZoom` + `axisPointer: { type: 'cross' }` + `toolbox` + `brush` + `connect` 等交互件开箱即用；6.0 新增的 Matrix 坐标系与 `brokenAxis` 对“多窗格联动 + 停牌断点”场景直接利好。
- **短板**：金融指标、复权、最后价格虚线等需自行实现；`candlestick` 不支持 `large/largeThreshold`（性能不如 `line` 的 LTTB 采样），5k+ 根时需配合 `sampling` 与 `progressive`。
- **结论**：作为通用底座继续保留的理由最充分。

#### KLineChart

- **优势**：为 K 线而生，指标、分时、周期切换、样式主题、覆盖物（画线）都是内置 API（`createIndicator / createOverlay / setStyles`），比在 ECharts 上手写 MA/BOLL/MACD/KDJ 省 60% 以上代码；10.0.x 的 `DataLoader + setPeriod` 对 A 股日/周/月/分钟的多周期扩展非常贴合；gzip 40KB 对移动端友好。
- **短板**：通用图表能力为零，若替换则热力图/回测曲线仍需保留 ECharts，形成双库并存；Pro 版（`@klinecharts/pro`）文档与版本成熟度不如核心库。
- **结论**：若下一阶段要把 K 线做成“专业看盘级”（多指标切换、画线、复权、周期），KLineChart 是最省力路径；可考虑 **ECharts 管仪表盘、KLineChart 管 K 线详情页**的分工。

#### lightweight-charts

- **优势**：体积最小、渲染最快（纯 canvas，前端每帧只做 `update` 增量），`panes` + `priceScaleOptions` + `priceLine` + `markers` 对“主图+成交量+指标副图”天然支持；社区插件生态（绘图工具、指标封装）丰富。
- **短板**：无内置指标、无 `dataZoom slider`（需自制时间轴控件）、无复权/周期聚合等 A 股语义；从 ECharts 迁移需重写 tooltip/legend 体系；署名要求对白标场景不友好。
- **结论**：适合“只做轻量预览/行情条”的场景，不适合一口气替换主图。

#### Highcharts Stock

- **优势**：开箱最全（`navigator / rangeSelector / compare / ordinal axis / boost`），对“券商级看盘”做到 90 分。
- **短板**：商业授权是硬门槛（EmoQunt 若未来开源商用/闭源商用均需付费），包体积与定制自由度不如前三者。
- **结论**：不推荐；除非团队愿意为 Highcharts 生态付费并接受其样式约束。

> 小结：**继续以 ECharts 为主**，在 K 线详情页按需引入 **KLineChart** 作为专业增强是性价比最高的演进路线；lightweight-charts 可作为后续性能对比的备选，Highcharts 不考虑。

---

## 三、主流行情平台的 K 线交互范式

调研 TradingView、同花顺、东方财富、雪球、富途的公开文档与可观测行为，提炼出“用户认为理所当然”的 12 项标准交互，未做到的会被视为缺陷。

| 交互 | 说明 | 标杆来源 |
|---|---|---|
| **十字光标 + OHLC 数值面板** | 鼠标移动时 `cross` 轴指针跟随，悬浮面板显示 `开/高/低/收/成交量/涨跌幅`，数值颜色跟涨跌（红涨绿跌/绿涨红跌） | TradingView 超级图表设置 [^tv-cross]；ECharts `axisPointer: { type: 'cross' }` 示例 |
| **周期切换** | 日/周/月/季/年 + 分钟（1/5/15/30/60）+ Tick；切换时自动聚合（周线取周五收盘） | TradingView 周期文档 [^tv-period]；东方财富“多周期同列” [^em-period] |
| **复权切换** | 前复权/后复权/不复权；A 股分红送股场景必须，切换后 Y 轴与指标重算 | 同花顺/东方财富 K 线工具栏常规能力；KLineChart `setPeriod` + 数据层重取 |
| **指标叠加 vs 副图** | 主图叠加：MA/EMA/BOLL/SAR；副图：VOL/MACD/KDJ/RSI/WR/OBV/DMI；支持多副图 + 可折叠 | TradingView 指标面板；KLineChart “蜡烛兼容指标”清单 [^kline-indicator] |
| **量价颜色联动** | 成交量柱颜色跟 K 线涨跌（`close >= open` 为涨色） | 本项目已实现；ECharts 官方“上证指数”示例同款 |
| **涨跌停/停牌标注** | 触及 10%/20% 涨跌停时在 K 线上打 `markPoint`，停牌日在 X 轴断点或灰色占位 | Highcharts `ordinal` 轴、ECharts 6 `brokenAxis` |
| **滚轮缩放 + 按住拖动** | `inside` dataZoom：滚轮缩放、按住拖动平移；移动端双指缩放、单指拖动、惯性滚动 | ECharts `dataZoom: { type: 'inside', zoomOnMouseWheel, moveOnMouseDrag }`；lightweight-charts `handleScale/handleScroll/kineticScroll` |
| **数据窗口滑块** | 底部 `slider` 缩略预览 + 刷选，适合 半年/一年 长度的快速定位 | ECharts `dataZoom: { type: 'slider' }`；Highcharts `navigator` |
| **最后价格虚线** | 最新价在价格轴画虚线 + 右侧标签，实时更新时闪动 | lightweight-charts `createPriceLine({ price, color, lineStyle: Dashed })`；ECharts `markLine: { data: [{ yAxis: lastClose }] }` |
| **价格轴格式化** | 千分位 + 小数位跟 `tickSize`（A 股 0.01，港股 0.01，美股 0.01/0.0001），Y 轴 `axisLabel.formatter` | ECharts `yAxis.axisLabel.formatter: v => v.toLocaleString('zh-CN', { minimumFractionDigits: 2 })` |
| **坐标轴联动** | 主图与成交量/指标副图共用 X 轴，`dataZoom` 与 `axisPointer` 联动 | ECharts `axisPointer.link: { xAxisIndex: 'all' }` / `connect` 多图联动示例 |
| **时间轴断点** | 跳过非交易日/停牌日的空白，`category` 轴或 `brokenAxis` 实现 | ECharts 官方 “Intraday Chart with Breaks” 示例；Highcharts `xAxis.ordinal: true` |

[^tv-cross]: TradingView 帮助中心《如何配置您的超级图表》对十字光标、价格坐标、视觉元素的配置说明 — https://cn.tradingview.com/support/solutions/43000748166/
[^tv-period]: TradingView 帮助中心《超级图表入门指南》对时间周期的定义 — https://cn.tradingview.com/support/solutions/43000746464/
[^em-period]: 东方财富期货帮助中心《多周期同列功能说明》对“不同周期 K 线联动缩放、十字光标联动”的说明 — https://qhweb.eastmoney.com/help/2255544.html

---

## 四、可视化最佳实践

### 1. 颜色语义

- **A 股红涨绿跌、美股绿涨红跌**是行业约定，本项目 `HomeView.vue` 已按 `market` 区分 `upColor/downColor`，符合预期。国际产品通常给用户可切换的“涨跌色”开关，建议保留当前按市场自动区分，并为色弱用户提供“涨跌色切换”设置项（与 `ui` store 一并持久化）。
- **色弱友好**：不要仅用红/绿区分，叠加形状（`▲/▼`、实心/空心蜡烛）、边框描边与文字标签。本项目自选徽章已用 `▲/▼ + ±x.xx%` 文字冗余，值得保持；K 线可在 `itemStyle.borderColor` 上加深描边提升对比度。

### 2. 蜡烛宽度与间距

- ECharts `series-candlestick.barWidth / barMinWidth / barMaxWidth` 需随数据密度自适应：180 根时 6–10px，730 根时 2–4px 并开启 `sampling`。KLineChart/lightweight-charts 会自动按 `barSpace` 计算，无需手动。
- 过宽会导致 1 年数据挤压、过窄会导致日线看不清影线，建议按 `data.length` 分档设置。

### 3. 叠加线配色

- MA/EMA 叠加建议用 **非红绿** 的区分色（项目现有 `#f59e0b`/`#667eea`/`#10b981` 已避开红绿），BOLL 用同色系的实线+半透明带状。避免与蜡烛涨跌色冲突。

### 4. 量价联动

- 成交量柱颜色跟 `close >= open` 保持一致是标杆做法（项目已实现 `volumes.map((v,i) => ohlcv[i][1] >= ohlcv[i][0] ? upColor : downColor)`），值得保留。

### 5. 大数据量性能

| 场景 | ECharts 策略 | lightweight-charts 策略 | KLineChart 策略 |
|---|---|---|---|
| 几百根 | 直接 `setOption` 全量 | `setData` 全量 | `applyNewData` 全量 |
| 几千根（730 日） | `series.sampling: 'lttb'` + `large: true` + `progressive: 1000`；滑窗用 `dataZoom` | `series.update` 增量 + `timeScale` 虚拟化，官方宣称 10k+ 仍流畅 | `updateData` 增量 + 内置虚拟化 |
| 实时追加 | `appendData`（仅 `line/bar` 支持，`candlestick` 不支持，需 `setOption` 增量替换） | `series.update(bar)` 单点追加最佳 | `updateData(bar)` 单点追加 |

> ECharts 的 `sampling` 仅对 `line` 系列生效，`candlestick` 需靠 `dataZoom` 视口裁剪 + 后端 `days` 限流（如项目 `get_kline` 的 `max 730`）来控量；若未来做分钟级，需后端分页 + 前端虚拟滚动。

### 6. 移动端适配

- `grid` 边距在窄屏收窄（`left: '8%'` → `left: '12'` 像素）、Y 轴标签 `margin` 缩小。
- `dataZoom.slider` 在触摸设备上保留但高度降低（`height: 20`），`inside` 手势开启 `moveOnMouseMove` 与双指缩放。
- tooltip 在移动端改 `trigger: 'axis'` + `position: 'top'` 避免遮挡，或改用固定顶部数值面板（TradingView 风格）。

---

## 五、ECharts K 线具体增强点（本项目大概率继续用 ECharts）

> 以下均基于 `https://echarts.apache.org/en/option.html` 的 `series-candlestick / series-custom / components` 一手文档与官方示例。

### 1. `candlestick + custom` 做美式 K 线与量价分窗

- ECharts 的 OHLC 美式线可通过 `series-custom` 的 `renderItem` 自绘（官方归类于 `series-custom`），与 `candlestick` 复用同一 `xAxis`。量价分窗则用本项目已有的双 `grid / xAxis / yAxis` + `xAxisIndex/yAxisIndex` 方案。
- 参考：`series-candlestick` — https://echarts.apache.org/en/option.html#series-candlestick ；`series-custom` — https://echarts.apache.org/en/option.html#series-custom ；示例 “OHLC Chart” — https://echarts.apache.org/examples/en/index.html

### 2. `markLine / markPoint` 标注买卖点与信号

- 买卖点用 `markPoint: { data: [{ coord: [date, price], value: 'B/S', itemStyle }] }`，止盈止损用 `markLine: { data: [{ yAxis: price, label: { formatter: '止损' } }] }`。`candlestick` 的 Y 值是四元组，`markLine` 的 `yAxis` 取收盘价维度即可。
- 本项目回测结果天然有交易序列，下一步可把 `backtest_manager` 的成交点透传到 `/api/kline` 或 `/api/backtest/run` 的扩展字段，前端直接映射为 `markPoint`。
- 参考：`series-candlestick.markLine` — https://echarts.apache.org/en/option.html#series-candlestick.markLine ；`series-candlestick.markPoint` — https://echarts.apache.org/en/option.html#series-candlestick.markPoint

### 3. `visualMap` 分段着色

- `visualMap: { type: 'piecewise', dimension: 1, pieces: [{ gt: 0, color: upColor }] }` 可按涨跌幅给蜡烛/成交量上色，或按成交量阈值给量柱上色。对“放量/缩量”一目了然。
- 参考：`visualMap` — https://echarts.apache.org/en/option.html#visualMap

### 4. `dataZoom` inside + slider 组合

- 本项目已用 `dataZoom: [{ type: 'inside', xAxisIndex: [0,1] }, { type: 'slider', xAxisIndex: [0,1] }]`，下一步可加上 `zoomOnMouseWheel: true, moveOnMouseMove: true, preventDefaultMouseMove: true` 与 `minValueSpan` 约束最小视口（如 30 根）。
- 参考：`dataZoom` — https://echarts.apache.org/en/option.html#dataZoom ；`dataZoom-inside` — https://echarts.apache.org/en/option.html#dataZoom-inside

### 5. `connect` 多图联动

- 回测页的“净值/回撤/日收益”三图、首页的“主图/成交量/指标副图”可用 `echarts.connect([chartA, chartB])` 联动 `dataZoom` 与 `axisPointer`，实现 TradingView 式的多窗格同步。
- 参考：`echarts.connect` — https://echarts.apache.org/en/api.html#echarts.connect ；示例 “Axis Pointer Link and Touch” — https://echarts.apache.org/examples/en/index.html

### 6. `brush` 区间选择

- 仪表盘上对 K 线做刷选（框选一段回测区间）用 `brush: { toolbox: ['rect','clear'], xAxisIndex: 0 }`，`brushSelected` 事件回调可触发二次回测或跳转。
- 参考：`brush` — https://echarts.apache.org/en/option.html#brush ；示例 “Candlestick Brush” — https://echarts.apache.org/examples/en/index.html

### 7. 其它可直接复用的官方示例

| 示例 | 解决的问题 | 链接 |
|---|---|---|
| Basic Candlestick | candlestick 最小可用配置 | https://echarts.apache.org/examples/en/index.html |
| Large Scale Candlestick | 5k+ 蜡烛的性能基线 | 同上 |
| ShangHai Index / ShangHai Index, 2015 | 量价分窗 + dataZoom 标准写法 | 同上 |
| Axis Pointer Link and Touch | 多图十字光标联动 + 移动端触摸 | 同上 |
| Matrix Stock Application (v6) | 多资产矩阵 + 交易深度图（ECharts 6 新增） | https://echarts.apache.org/handbook/en/basics/release-note/v6-feature/ |
| Intraday Chart with Breaks | 分时断点（跳过非交易时段） | https://echarts.apache.org/examples/en/index.html |

---

## 六、本项目现状盘点（只读代码）

### 1. Jinja2 前端（`web/templates/`）

| 模板 | K 线/图表相关现状 | 缺口 |
|---|---|---|
| `base.html` | 顶部导航，无图表；全局 `showLoading` 遮罩 | — |
| `backtest_form.html` | 表单：市场/策略/代码/资金/日期/费率；本地持久化 `emoqunt:backtest_form`；无预览图 | 缺 K 线预览 |
| `backtest_result.html` | **静态图**：`equity_chart_url / drawdown_chart_url / dashboard_url` 三张 `matplotlib` 出图（`src/backtest/backtest_manager.py:run_backtest_with_charts`），非交互 | 无交互 K 线、无买卖点、无成交量联动 |
| `index.html` / `sentiment_*` / `daily_recommend.html` | 非 K 线页 | — |

### 2. Vue3 SPA（`frontend/src/`）

| 位置 | 现状 | 缺口 |
|---|---|---|
| `composables/useECharts.ts` | 按需注册：`CanvasRenderer + LineChart/BarChart/CandlestickChart/TreemapChart + Title/Tooltip/Legend/Grid/DataZoom/Toolbox/VisualMap`；未注册 `BrushComponent` | 缺 `BrushComponent`（区间刷选） |
| `views/HomeView.vue` | **主图 K 线**：`candlestick` + `bar` 成交量双窗格、`axisPointer: cross`、MA5/20/60 叠加（前端 `calcMA` 计算）、`dataZoom inside+slider`（60–100%）、按 `market` 红涨绿跌、量柱颜色联动、MA 开关持久化、重置缩放；数据源 `klineApi.get(code, market, 180)` | 缺：周期/复权切换、更多指标（BOLL/MACD/KDJ/RSI/VOL 副图）、买卖点标注、最后价格虚线、价格轴千分位、停牌断点、大数据采样、移动端手势调优、多图 `connect` |
| `views/BacktestView.vue` | 回测三图：`equityOption`（策略 vs 基准虚线 + `areaStyle`）、`drawdownOption`（`areaStyle` 红色）、`returnsOption`（`bar` 红绿按正负）；均有 `dataZoom inside+slider` + `toolbox` | 缺：与 K 线联动、交易点标注、`brush` 区间重跑 |
| `api/index.ts` / `api/types.ts` | `klineApi.get(stock_code, market, days)` → `GET /api/kline` 返回 `{ code, market, name, dates, ohlcv: [open,close,low,high], volumes }` | 后端未返回买卖点/复权标记/周期聚合 |
| `layouts/AppLayout.vue` | 侧边栏 + 暗色主题 + 面包屑，与图表无关 | — |

### 3. 后端 `/api`（`web_app.py` + `src/services/kline.py`）

| 端点 | 现状 | 缺口 |
|---|---|---|
| `GET /api/kline?stock_code&market&days` | `plain def`（走线程池），`Stock(code, market).get_stock_data(adjust='qfq'(美股)/'hfq'(A股))`，`days` 钳制 30–730，重命名列后取 `tail(days)`，返回 `{ dates, ohlcv, volumes }`；无复权/周期参数 | 缺：`adjust`/`period` 透传、`ohlcv` 含 `turnover`（供 EMV/AVP）、买卖点可选字段 |
| `POST /api/backtest/run` | `run_backtest_json` 返回 `{ dates, equity_curve, benchmark_curve, drawdown, daily_returns, metrics, risk_report, market }`，ECharts 前端自绘 | 缺：`trades: [{ date, price, side }]` 供 K 线打点 |
| `GET /api/market/sectors` / `breadth` | 供热力图/市场宽度，与 K 线无关 | — |

---

## 七、对本项目的优化建议清单

> 优先级：P0（下个迭代必做，收益高/成本低） → P1（季度内） → P2（中长期/待验证）。工作量以“前端人日”估算（不含后端数据接入）。

### P0

| # | 优化项 | 涉及库/组件 | 工作量 | 说明 |
|---|---|---|---|---|
| 1 | **K 线主图补齐「最后价格虚线 + 价格轴千分位」** | ECharts `series-candlestick.markLine` + `yAxis.axisLabel.formatter` | 0.5 天 | `markLine: { symbol: 'none', lineStyle: { type: 'dashed' }, data: [{ yAxis: lastClose }] }`；Y 轴 `formatter: v => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })`。标杆一致，用户感知强。 |
| 2 | **价格/成交量数值面板固定化 + 涨跌着色** | ECharts `tooltip` 优化（`position: 'top'` 或固定 DOM 面板） | 0.5 天 | 现有 `tooltip.formatter` 已显示 OHLC/MA/成交量，下一步把面板固定在图顶部（TradingView 风格），数值按 `close >= open` 染红/绿，避免跟随鼠标遮挡。|
| 3 | **移动端手势与布局收敛** | ECharts `dataZoom.inside` + CSS `grid` | 0.5 天 | `inside` 加 `zoomOnMouseWheel/moveOnMouseDrag/moveOnMouseMove`，`slider` 在窄屏降低高度；`grid.left/right` 用像素值在 `<768px` 时收窄。|
| 4 | **按数据量自适应蜡烛宽度与采样** | ECharts `barWidth/barMinWidth` + 后端 `days` 限流 | 0.5 天 | `days <=180` 时 `barWidth: 6`，`days >400` 时 `barWidth: 2, barMinWidth: 1`；`line` 叠加开 `sampling: 'lttb'`。|
| 5 | **回测结果页 K 线联动（买卖点标注）** | ECharts `markPoint` + 后端 `trades` 透传 | 1 天 | 后端 `run_backtest_json` 增 `trades` 字段，前端 `BacktestView.vue` 复用 `klineApi` 拉同期 K 线并以 `markPoint: { data: trades.map(t => ({ coord: [t.date, t.price], value: t.side==='buy'?'B':'S' })) }` 打点。|

### P1

| # | 优化项 | 涉及库/组件 | 工作量 | 说明 |
|---|---|---|---|---|
| 6 | **周期与复权切换** | `src/services/kline.py` 新增 `period/adjust` 参数 + 前端 `el-radio-group` | 2–3 天 | `GET /api/kline?period=day/week/month&adjust=qfq/hfq/none`，后端透传给 `Stock.get_stock_data`；周/月线由 akshare/baostock 侧聚合或后端重采样。A 股必备。|
| 7 | **指标副图（VOL + MACD/RSI 二选一）** | ECharts 三 `grid`（主图/成交量/指标）+ 前端指标计算 | 2 天 | 成交量已有一窗，再加一窗放 MACD（`DIF/DEA/柱`）或 RSI；计算可在前端（如 `technicalindicators` npm）或后端；`legend` 与 `dataZoom xAxisIndex: [0,1,2]` 联动。KLineChart 方案则一行 `createIndicator('MACD')`，但会引入双库。|
| 8 | **BOLL/MA 叠加可配置** | ECharts `line` 叠加 + `legend.selected` | 1 天 | 现有 MA5/20/60 为固定，改为 `el-checkbox-group` 选 MA/BOLL/EMA，BOLL 用两条 `line` + `areaStyle` 带状；颜色避开红绿。|
| 9 | **多图 `connect` 联动（回测三图 + K 线）** | `echarts.connect` | 0.5 天 | `echarts.connect([equityChart, drawdownChart, returnsChart])` 与 `klineChart` 的 `dataZoom` 联动，需在 `useECharts` 中暴露 `chart` 实例。|
| 10 | **色弱友好与主题一致性** | CSS 变量 + `itemStyle` | 0.5 天 | 在 `ui` store 增 `candleColors` 设置（红涨绿跌/绿涨红跌/蓝橙方案），持久化；暗色模式下蜡烛边框加深。|

### P2

| # | 优化项 | 涉及库/组件 | 工作量 | 说明 |
|---|---|---|---|---|
| 11 | **区间刷选（brush）触发二次回测** | ECharts `BrushComponent` + `brushSelected` 事件 | 1 天 | 需在 `useECharts.ts` 注册 `BrushComponent`，K 线上框选后把 `range` 回填到回测表单日期。|
| 12 | **引入 KLineChart 承载专业看盘页** | `klinecharts` 10.x + 独立路由 `views/KlineProView.vue` | 3–5 天 | 新开 `/spa/kline-pro` 专业页，用 `init/dispose + setDataLoader + createIndicator` 实现多周期/多指标/画线；仪表盘看板仍用 ECharts，避免全量替换风险。|
| 13 | **分钟级与分时断点** | 后端分钟数据源 + ECharts `brokenAxis` / `category` 轴 | 3 天 | 需新增 `type: '1m/5m'` 的数据源分支，X 轴跳过非交易时段（ECharts 6 `brokenAxis` 或 `category`）。|
| 14 | **实时追加（WebSocket/SSE 轮询）** | 前端 `series.update` 增量 + 后端推送 | 2 天 | 轻量场景用 `setInterval(klineApi.get, 60s)` + `chart.setOption({ series: [{ data: newOhlcv }] })`；重度场景再上 WebSocket。|

### 决策记录

- **不全量替换 ECharts**：仪表盘已深度依赖 ECharts（热力图 `treemap`、回测三图、市场宽度），替换成本与回归风险高于收益；K 线增强优先在 ECharts 上做增量。
- **KLineChart 作为专业页增量而非替换**：其指标/周期/画线能力对“看盘”场景价值明确，但双库并存比一刀切更稳妥。
- **不引入 Highcharts Stock**：商业授权与 EmoQunt 的开源定位冲突，且 ECharts + KLineChart 已覆盖其能力。
- **买卖点标注依赖后端 `trades` 透传**：前端无法从现有 `/api/backtest/run` 推断交易点，需后端先暴露。

---

## 八、参考链接

- ECharts 官网：https://echarts.apache.org/ · 配置项 `series-candlestick`：https://echarts.apache.org/en/option.html#series-candlestick · `series-custom`：https://echarts.apache.org/en/option.html#series-custom · `dataZoom`：https://echarts.apache.org/en/option.html#dataZoom · `markLine/markPoint`：https://echarts.apache.org/en/option.html#series-candlestick.markLine · `visualMap`：https://echarts.apache.org/en/option.html#visualMap · `brush`：https://echarts.apache.org/en/option.html#brush · 示例集：https://echarts.apache.org/examples/en/index.html · 6.0 特性：https://echarts.apache.org/handbook/en/basics/release-note/v6-feature/
- KLineChart 官网：https://www.klinecharts.com/ · 快速上手：https://klinecharts.com/guide/quick-start.html · 技术指标：https://klinecharts.com/en-US/guide/indicator · GitHub：https://github.com/klinecharts/KLineChart · npm：https://www.npmjs.com/package/klinecharts
- lightweight-charts 官网：https://www.tradingview.com/lightweight-charts/ · 文档：https://tradingview.github.io/lightweight-charts/ · API：https://tradingview.github.io/lightweight-charts/docs/api · GitHub：https://github.com/tradingview/lightweight-charts · v5 发布：https://www.tradingview.com/blog/en/tradingview-lightweight-charts-version-5-50837/
- Highcharts Stock：https://www.highcharts.com/products/stock/ · Demo：https://www.highcharts.com/demo/stock/candlestick-and-volume · 商店授权：https://shop.highcharts.com/
- TradingView 帮助中心：超级图表设置 — https://cn.tradingview.com/support/solutions/43000748166/ · 入门指南 — https://cn.tradingview.com/support/solutions/43000746464/
- 东方财富“多周期同列”：https://qhweb.eastmoney.com/help/2255544.html
- 本仓库现状锚点：`frontend/src/composables/useECharts.ts` · `frontend/src/views/HomeView.vue`（`klineOption`） · `frontend/src/views/BacktestView.vue` · `frontend/src/api/index.ts`（`klineApi`） · `src/services/kline.py`（`get_kline`） · `web_app.py`（`GET /api/kline`）

---

## 九、落地记录（2026-08-27 本轮迭代）

基于本文档结论，在**不引入新库、继续用 ECharts 增量**的决策下，已完成：

| 对应建议 | 已落地内容 | 涉及文件 |
|---|---|---|
| P1-6 周期与复权切换 | `/api/kline` 新增 `period=day/week/month` 与 `adjust=qfq/hfq/nfq` 参数；周/月由服务端按真实交易日分组聚合（周线标签取周五、月线取月末最后交易日、ISO 跨年周归组）；前端工具栏周期 radio + 复权 select，选择持久化到 localStorage | `src/services/kline.py` · `web_app.py` · `frontend/src/api/index.ts` · `frontend/src/views/HomeView.vue` |
| P0-1 最后价格虚线 + 价格轴千分位 | `candlestick.markLine` 最新价虚线（颜色跟最后一根涨跌、右端价格标签）+ 主图 Y 轴 `toLocaleString` 千分位两位小数 | `frontend/src/views/HomeView.vue` |
| P1-7 指标副图 | 第三窗格副图指标 MACD(12,26,9)/KDJ(9,3,3)/RSI(6,12,24)，前端计算口径对齐通达信（SMA(U,N,1) 平滑、hist=(DIF−DEA)×2），多窗格共享 X 轴 dataZoom + `axisPointer.link` 十字光标联动 | 同上 |
| P1-8 BOLL 叠加可配置 | 主图叠加改为 无/MA/BOLL 三选；BOLL(20,±2σ 总体标准差)上中下轨虚线；旧 `emoqunt:kline_ma` 开关自动迁移为新偏好键 | 同上 |
| P0-2 tooltip 数值增强 | OHLC 按"相对昨收涨跌"着色、新增涨跌幅/振幅行、成交量 亿/万自适应格式化、附当前主图/副图指标读数 | 同上 |
| P0-3 移动端手势与蜡烛自适应 | `dataZoom.inside` 显式开启滚轮缩放/拖动平移并约束最小视口 15 根；蜡烛宽度按数据密度分档（≤70根 9px → >420根 2px）；图表高度 460→520px 容纳副图 | 同上 |

技术决策补充：

- **复权默认值变化**：前端默认「前复权」（对齐同花顺/东财主流行情软件）；后端不传 `adjust` 时仍保持旧默认（A股 hfq、美股 qfq），保证既有调用方行为不变。
- **指数代码路由（2026-08-27 追加修复）**：`/api/kline` 此前把指数代码送进个股回退链导致沪深300 等返回空数据、上证预设实际取到平安银行股价。现新增 `kind=index` 参数路由到 `data_manager.get_index_data` 指数链；无歧义代码（000300/399xxx）自动识别，二义的 000001 默认保持个股行为、前端预设显式传 `kind`；指数响应标记 `kind:index` 且忽略复权。涉及 `src/services/kline.py` · `web_app.py` · `frontend/src/api/*` · `frontend/src/stores/watchlist.ts`(revive 迁移) · `HomeView.vue`。
- **状态更新策略**：`<v-chart>` 加 `:update-options="{ notMerge: true }"`，避免切换副图指标增删窗格时 ECharts 默认 merge 留下残影系列。
- **验证记录**：合成数据单测验证周/月聚合边界（周五标签、跨年 ISO 周）；真实链路冒烟通过（平安银行 日/周/月 + 美股 AAPL，adjust 三个档位透传正确）；`npm run build`（vue-tsc 类型检查）通过。
- **待办（后续迭代）**：P0-5 回测买卖点标注（依赖后端 `trades` 透传）、P1-9 `echarts.connect` 多图联动、P2 brush 区间刷选与 KLineChart 专业看盘页评估。

