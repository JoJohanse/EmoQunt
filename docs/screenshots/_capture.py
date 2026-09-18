"""README 截图采集脚本：用系统 Edge 无头浏览器访问本机 FastAPI，截取新版界面。

用法:
    conda run -n qdt python docs/screenshots/_capture.py             # 中文版全量（覆盖默认文件名）
    conda run -n qdt python docs/screenshots/_capture.py --lang en   # 英文版全量（输出 *-en.png）
    conda run -n qdt python docs/screenshots/_capture.py --quick     # 仅首页/K线截图

说明：
- 全新浏览器上下文首访 /spa/ 会弹出 driver.js 新手导览（7 步），脚本先截导览，
  再逐步走完后关闭，保证后续截图无遮罩。
- --lang en 通过 emoqunt_lang cookie 切换界面语言（SPA 首访读 cookie 定语言，
  Jinja2 页面由中间件读同一 cookie），英文截图统一加 -en 后缀，供英文版 README（README.md）引用。
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).parent
VIEWPORT = {"width": 1440, "height": 960}
LANG = "en" if "--lang" in sys.argv and "en" in sys.argv else "zh"
SUFFIX = "-en" if LANG == "en" else ""
QUICK = "--quick" in sys.argv

# 双语 UI 文案（与 frontend/src/locales/*.ts 保持同步）
T = {
    "zh": {
        "dark": "切换到暗色模式",
        "light": "切换到亮色模式",
        "tour_done": "完成",
        "start_date": "开始日期",
        "end_date": "结束日期",
        "run_backtest": "运行回测",
        "equity_ready": "累计收益曲线",
        "trades_section": "买卖点标注",
        "ai_button": "AI 助手",
        "chat_placeholder": "输入问题，回车发送（Shift+回车换行）",
        "tool_card_link": "在首页查看主图",
        "period_week": "周",
        "period_day": "日",
    },
    "en": {
        "dark": "Switch to dark mode",
        "light": "Switch to light mode",
        "tour_done": "Done",
        "start_date": "Start Date",
        "end_date": "End Date",
        "run_backtest": "Run Backtest",
        "equity_ready": "Cumulative Return",
        "trades_section": "Backtest K-line · Trade Markers",
        "ai_button": "AI Assistant",
        "chat_placeholder": "Ask a question, press Enter to send (Shift+Enter for a new line)",
        "tool_card_link": "View main chart on Home",
        "period_week": "W",
        "period_day": "D",
    },
}[LANG]


def shot(page, name: str, **kwargs) -> None:
    """按语言后缀落盘并打印进度。"""
    path = OUT / f"{name}{SUFFIX}.png"
    page.screenshot(path=str(path), **kwargs)
    print(f"{path.name} done")


def dismiss_tour(page) -> None:
    """若首访导览弹出，先截图存档，再逐步点完关闭。"""
    try:
        page.wait_for_selector(".driver-popover", timeout=8000)
    except Exception:
        return  # 无导览（已看过）
    page.wait_for_timeout(600)
    shot(page, "spa-home-tour")
    for _ in range(8):
        if not page.locator(".driver-popover").count():
            break
        btn = page.locator(".driver-popover-buttons button", has_text=T["tour_done"])
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
        if LANG == "en":
            # SPA 首访读 emoqunt_lang cookie 定语言；Jinja2 页面同 cookie 生效
            ctx.add_cookies([{"name": "emoqunt_lang", "value": "en-US", "url": BASE}])
        page = ctx.new_page()

        # 1) SPA 首页（亮色，等行情/图表渲染；首访先处理新手导览）
        page.goto(f"{BASE}/spa/", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        dismiss_tour(page)
        page.wait_for_timeout(8000)
        shot(page, "spa-home-light", full_page=True)

        # 2) SPA 首页（暗色）
        page.locator(f'button[title="{T["dark"]}"]').click()
        page.wait_for_timeout(1500)
        shot(page, "spa-home-dark", full_page=True)
        # 切回亮色，保持默认偏好
        page.locator(f'button[title="{T["light"]}"]').click()
        page.wait_for_timeout(800)

        # 2b) K 线看板特写：蜡烛 + MA 叠加 + 最新价虚线 + MACD 副图（上证指数走指数链）
        kline_card = page.locator(".kline-card")
        kline_card.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        shot(page, "spa-kline")

        # 2c) 切周线：服务端聚合 + 三窗格联动（选择器限定在 K 线工具栏内，
        #     避免与"自选分布"卡片的"当日涨跌"维度按钮歧义）
        kline_toolbar = page.locator(".kline-toolbar")
        kline_toolbar.locator(".el-radio-button", has_text=T["period_week"]).first.click()
        page.wait_for_timeout(6000)
        shot(page, "spa-kline-week")
        # 切回日线，保持默认偏好
        kline_toolbar.locator(".el-radio-button", has_text=T["period_day"]).first.click()
        page.wait_for_timeout(4000)

        if QUICK:
            ctx.close()
            browser.close()
            return 0

        # 3) SPA 回测：跑一段 2025 区间（外部数据源对该区间稳定），截结果页
        page.goto(f"{BASE}/spa/backtest", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        start = page.get_by_role("combobox", name=T["start_date"])
        start.click()
        start.fill("2025-03-01")
        start.press("Enter")
        page.wait_for_timeout(500)
        end = page.get_by_role("combobox", name=T["end_date"])
        end.click()
        end.fill("2025-09-30")
        end.press("Enter")
        page.wait_for_timeout(800)
        page.get_by_role("button", name=T["run_backtest"]).click()
        page.get_by_text(T["equity_ready"]).wait_for(timeout=180_000)
        # 等回测 K 线（买卖点标注）加载完成
        page.wait_for_timeout(8000)
        shot(page, "spa-backtest", full_page=True)
        # 买卖点标注特写（后端 trades 透传 + markPoint B/S + 成本均价 markLine）
        trades_title = page.locator(".section-title", has_text=T["trades_section"])
        trades_title.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        shot(page, "spa-backtest-trades")

        # 4) SPA 策略列表
        page.goto(f"{BASE}/spa/strategies", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        shot(page, "spa-strategies", full_page=True)

        # 4b) 策略库 v2：代码策略卡片网格 + 详情页（参数/代码/版本/回测/调优 Tabs；id=1 为既有示例策略）
        page.goto(f"{BASE}/spa/strategy-library", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        shot(page, "spa-strategy-library", full_page=True)
        page.goto(f"{BASE}/spa/strategy-library/1", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        shot(page, "spa-strategy-detail", full_page=True)

        # 4c) 运行历史 + 调优任务详情（归一化净值对比 + 组合表；task 3 为浏览器实测产物）
        page.goto(f"{BASE}/spa/runs", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        shot(page, "spa-runs", full_page=True)
        page.goto(f"{BASE}/spa/tuning/3", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        shot(page, "spa-tuning", full_page=True)

        # 4d) 因子库：列表 + 详情（代码 Tab；id=1 动量因子）
        page.goto(f"{BASE}/spa/factor-library", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        shot(page, "spa-factor-library", full_page=True)
        page.goto(f"{BASE}/spa/factor-library/1", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        shot(page, "spa-factor-detail", full_page=True)

        # 5) Jinja2 舆情分析（经典版前端；服务端爬数据可能慢，goto 放宽超时且失败不致命）
        try:
            page.goto(f"{BASE}/sentiment", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(6000)
            shot(page, "web-sentiment", full_page=True)
        except Exception as e:
            print(f"web-sentiment skipped: {e}")

        # 6) AI 助手工具结果卡片（Generative UI；需 .env 配置 LLM API Key，失败不影响其余截图）
        try:
            page.goto(f"{BASE}/spa/", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.get_by_role("button", name=T["ai_button"]).click()
            box = page.get_by_role("textbox", name=T["chat_placeholder"])
            box.fill("帮我看看 000300 最近行情" if LANG == "zh" else "Show me the recent quote for 000300")
            box.press("Enter")
            page.wait_for_selector(f"text={T['tool_card_link']}", timeout=90_000)
            page.wait_for_timeout(2500)
            shot(page, "spa-chat-tool-card")
        except Exception as e:
            print(f"spa-chat-tool-card skipped: {e}")

        ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
