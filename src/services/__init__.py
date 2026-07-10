"""EmoQunt 服务层。

将原 web_app.py 中寄居在路由处理器里的业务编排逻辑下沉为深模块。
路由层（web_app.py）变为薄适配器，仅负责 HTTP 请求解析与响应封装，
业务逻辑通过本层接口调用。

服务模块：
    - strategies: 策略列表/详情/创建/更新/删除（双前端共享）
    - sentiment: 舆情数据获取/刷新（双前端共享）
    - recommend: 每日推荐获取/刷新（双前端共享）
    - kline: K线 OHLCV 数据获取
"""
