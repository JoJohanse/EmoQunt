"""README 截图采集脚本：用系统 Edge 无头浏览器访问本机 FastAPI，截取新版界面。

用法:
    conda run -n qdt python docs/screenshots/_capture.py           # 全量（含真实回测）
    conda run -n qdt python docs/screenshots/_capture.py --quick   # 仅首页/K线截图
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).parent
VIEWPORT = {"width": 1440, "height": 960}
QUICK = "--quick" in sys.argv


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

        # 1) SPA 首页（亮色，等行情/图表渲染）
        page.goto(f"{BASE}/spa/", wait_until="domcontentloaded")
        page.wait_for_timeout(12000)
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

        # 2c) 切周线：服务端聚合 + 三窗格联动
        page.locator(".el-radio-button", has_text="周").click()
        page.wait_for_timeout(6000)
        kline_card.screenshot(path=str(OUT / "spa-kline-week.png"))
        print("spa-kline-week.png done")
        # 切回日线，保持默认偏好
        page.locator(".el-radio-button", has_text="日").click()
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
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT / "spa-backtest.png"), full_page=True)
        print("spa-backtest.png done")

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

        ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
