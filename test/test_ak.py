import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm

# 设置matplotlib支持中文
plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# stock_data = ak.stock_zh_a_daily(symbol="sz000001", start_date="2025-01-01",end_date="2025-12-1")
# stock_data.to_csv("sz000001.csv", index=False)



# 读取股票数据
stock_data = pd.read_csv("sz000001.csv")

# 计算5日和20日均线
stock_data["ma5"] = stock_data["close"].rolling(window=5).mean()
stock_data["ma20"] = stock_data["close"].rolling(window=20).mean()

# 生成买入信号（ma5向上穿越ma20）
stock_data["buy_signal"] = (stock_data["ma5"] > stock_data["ma20"]) & (stock_data["ma5"].shift(1) <= stock_data["ma20"].shift(1))

# 生成卖出信号（ma5向下穿越ma20）
stock_data["sell_signal"] = (stock_data["ma5"] < stock_data["ma20"]) & (stock_data["ma5"].shift(1) >= stock_data["ma20"].shift(1))

# # 打印交易信号
# signals = stock_data[["date", "buy_signal", "sell_signal"]]
# print(signals)
# signals.to_csv("signals.csv", index=False)

# 将date列转换为datetime类型
stock_data["date"] = pd.to_datetime(stock_data["date"])

# 根据信号生成图表
plt.figure(figsize=(12, 6))
plt.plot(stock_data["date"], stock_data["close"], label="Close Price")
plt.plot(stock_data["date"], stock_data["ma5"], label="MA5")
plt.plot(stock_data["date"], stock_data["ma20"], label="MA20")
plt.scatter(stock_data["date"][stock_data["buy_signal"]], stock_data["close"][stock_data["buy_signal"]], marker="^", color="g", label="Buy Signal")
plt.scatter(stock_data["date"][stock_data["sell_signal"]], stock_data["close"][stock_data["sell_signal"]], marker="v", color="r", label="Sell Signal")
plt.legend()
plt.title("平安银行日均线曲线")
plt.xlabel("Date")
plt.ylabel("Price")

# 设置x轴日期显示格式和间隔
ax = plt.gca()
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))  # 每月显示一个刻度
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))  # 日期格式
plt.xticks(rotation=45)
plt.tight_layout()  # 调整布局，防止标签被截断
plt.savefig("平安银行日均线曲线.png")
plt.show()
