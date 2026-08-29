"""README 截图采集脚本：用系统 Edge 无头浏览器访问本机 FastAPI，截取新版界面。

用法:
    conda run -n qdt python docs/screenshots/_capture.py           # 全量（含真实回测）
    conda run -n qdt python docs/screenshots/_capture.py --quick   # 仅首页/K线截图

说明：全新浏览器上下文首访 /spa/ 会弹出 driver.js 新手导览（7 步），
脚本会先截导览，再逐步走完后关闭，保证后续截图无遮罩。
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).parent
VIEWPORT = {"width": 1440, "height": 960}
QUICK = "--quick" in sys.argv


def dismiss_tour(page) -> None:
    """若首访导览弹出，先截图存档，再逐步点完关闭。"""
    try:
        page.wait_for_selector(".driver-popover", timeout=8000)
    except Exception:
        return  # 无导览（已看过）
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "spa-home-tour.png"))
    print("spa-home-tour.png done")
    for _ in range(8):
        if not page.locator(".driver-popover").count():
            break
        btn = page.locator(".driver-popover-buttons button", has_text="完成")
        if btn.count():
            btn.click()
        else:
            page.locator(".driver-popover-next-btn").last.click()
        page.wait_for_timeout(500)


def main() -> int:
    with sync_playwright() as p:
        # 优先系统 Edge（免下载 chromium），回退 chrome
        for channel in ("msedge", "chrome"):
            try:
                browser = p.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                continue
        else:
            browser = p.chromium.launch(headless=True)

        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        # 1) SPA 首页（亮色，等行情/图表渲染；首访先处理新手导览）
        page.goto(f"{BASE}/spa/", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        dismiss_tour(page)
        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT / "spa-home-light.png"), full_page=True)
        print("spa-home-light.png done")

        # 2) SPA 首页（暗色）
        page.locator('button[title="切换到暗色模式"]').click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "spa-home-dark.png"), full_page=True)
        print("spa-home-dark.png done")
        # 切回亮色，保持默认偏好
        page.locator('button[title="切换到亮色模式"]').click()
        page.wait_for_timeout(800)

        # 2b) K 线看板特写：蜡烛 + MA 叠加 + 最新价虚线 + MACD 副图（上证指数走指数链）
        kline_card = page.locator(".kline-card")
        kline_card.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        kline_card.screenshot(path=str(OUT / "spa-kline.png"))
        print("spa-kline.png done")

        # 2c) 切周线：服务端聚合 + 三窗格联动（选择器限定在 K 线工具栏内，
        #     避免与"自选分布"卡片的"当日涨跌"维度按钮歧义）
        kline_toolbar = page.locator(".kline-toolbar")
        kline_toolbar.locator(".el-radio-button", has_text="周").first.click()
        page.wait_for_timeout(6000)
        kline_card.screenshot(path=str(OUT / "spa-kline-week.png"))
        print("spa-kline-week.png done")
        # 切回日线，保持默认偏好
        kline_toolbar.locator(".el-radio-button", has_text="日").first.click()
        page.wait_for_timeout(4000)

        if QUICK:
            ctx.close()
            browser.close()
            return 0

        # 3) SPA 回测：跑一段 2025 区间（外部数据源对该区间稳定），截结果页
        page.goto(f"{BASE}/spa/backtest", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        start = page.get_by_role("combobox", name="开始日期")
        start.click()
        start.fill("2025-03-01")
        start.press("Enter")
        page.wait_for_timeout(500)
        end = page.get_by_role("combobox", name="结束日期")
        end.click()
        end.fill("2025-09-30")
        end.press("Enter")
        page.wait_for_timeout(800)
        page.get_by_role("button", name="运行回测").click()
        page.get_by_text("累计收益曲线").wait_for(timeout=180_000)
        # 等回测 K 线（买卖点标注）加载完成
        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT / "spa-backtest.png"), full_page=True)
        print("spa-backtest.png done")
        # 买卖点标注特写（后端 trades 透传 + markPoint B/S + 成本均价 markLine）
        trades_title = page.locator(".section-title", has_text="买卖点标注")
        trades_title.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "spa-backtest-trades.png"))
        print("spa-backtest-trades.png done")

        # 4) SPA 策略列表
        page.goto(f"{BASE}/spa/strategies", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "spa-strategies.png"), full_page=True)
        print("spa-strategies.png done")

        # 5) Jinja2 舆情分析（经典版前端）
        page.goto(f"{BASE}/sentiment", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        page.screenshot(path=str(OUT / "web-sentiment.png"), full_page=True)
        print("web-sentiment.png done")

        # 6) AI 助手工具结果卡片（Generative UI；需 .env 配置 LLM API Key，失败不影响其余截图）
        try:
            page.goto(f"{BASE}/spa/", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.get_by_role("button", name="AI 助手").click()
            box = page.get_by_role("textbox", name="输入问题，回车发送（Shift+回车换行）")
            box.fill("帮我看看 000300 最近行情")
            box.press("Enter")
            page.wait_for_selector("text=在首页查看主图", timeout=90_000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "spa-chat-tool-card.png"))
            print("spa-chat-tool-card.png done")
        except Exception as e:
            print(f"spa-chat-tool-card skipped: {e}")

        ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
