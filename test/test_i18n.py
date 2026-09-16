"""i18n 基础设施单元测试（src/utils/i18n.py + web_app.py 接线 + 目录完整性）。

覆盖：
- t() 兜底链：en 命中 / zh 兜底 / default / key 本身 / 插值
- vmsg()（en 与 zh，含参数）与 tr_error()（精确、参数化、未命中）
- set_request_lang() / normalize_lang() 归一（未知 → zh-CN）
- cookie 中间件写入 ContextVar（async 路由 + 线程池 def 路由）
- /set-lang：cookie 写入与开放重定向拒绝
- 模板接线：/ 首页按语言渲染（<html lang>、导航、页脚、window.__I18N__）
- 目录完整性：setup 自检 id、metric.* 键形状、js.* 前缀

运行：pytest test/test_i18n.py -v
（需在项目 conda 环境 qdt 中；与 test_backtest.py 一样手动注入 sys.path）
"""
import os
import re
import sys

import pytest

# 确保项目根在 sys.path（从 test/ 目录直接 pytest 时也生效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.utils.i18n import (  # noqa: E402
    DEFAULT_LANG,
    LANG_COOKIE,
    MESSAGES,
    SUPPORTED_LANGS,
    get_lang,
    i18n_js_bundle,
    normalize_lang,
    set_request_lang,
    t,
    tr_error,
    vmsg,
)

# web_app 会装配真实的中间件与 /set-lang 路由（TestClient 直连真实应用，不用 mock）
import web_app  # noqa: E402


def _ensure_probe_routes(app) -> None:
    """在真实 app 上挂两个探针路由（幂等），用于断言 ContextVar 传播。"""
    if getattr(app.state, "_i18n_probe_registered", False):
        return

    @app.get("/__i18n_probe")
    async def _i18n_probe_async():
        return {"lang": get_lang()}

    @app.get("/__i18n_probe_threadpool")
    def _i18n_probe_threadpool():
        return {"lang": get_lang()}

    app.state._i18n_probe_registered = True


_ensure_probe_routes(web_app.app)


@pytest.fixture()
def client():
    """不进入 lifespan：避免测试触发策略预热与 PostgreSQL/Redis 探测。"""
    from fastapi.testclient import TestClient
    return TestClient(web_app.app)


@pytest.fixture(autouse=True)
def _reset_lang():
    """每个用例前后把 ContextVar 复位为默认语言，避免用例互相污染。"""
    set_request_lang(DEFAULT_LANG)
    yield
    set_request_lang(DEFAULT_LANG)


# ---------------------------------------------------------------------------
# t() / vmsg() / tr_error()
# ---------------------------------------------------------------------------
class TestTranslate:
    """t() 的兜底链与插值。"""

    def test_english_hit(self):
        set_request_lang("en-US")
        assert t("nav.home") == "Home"
        assert t("footer.tagline") == "Making quantitative investing simpler"

    def test_chinese_default(self):
        set_request_lang("zh-CN")
        assert t("nav.home") == "首页"
        assert t("footer.tagline") == "让量化投资更简单"

    def test_english_falls_back_to_chinese_when_en_missing(self, monkeypatch):
        monkeypatch.setitem(MESSAGES, "test.onlyZh", {"zh": "只有中文"})
        set_request_lang("en-US")
        assert t("test.onlyZh") == "只有中文"

    def test_default_used_when_key_missing(self):
        set_request_lang("en-US")
        assert t("test.missing.key", "兜底文案") == "兜底文案"

    def test_key_itself_when_nothing_found(self):
        set_request_lang("en-US")
        assert t("test.missing.key") == "test.missing.key"

    def test_empty_default_is_honored(self):
        """default="" 属于有效兜底值（模板里 hint 常为空串）。"""
        set_request_lang("en-US")
        assert t("test.missing.key", "") == ""

    def test_params_interpolation(self):
        set_request_lang("en-US")
        assert t("common.opFailed", op="Backtest execution") == (
            "Backtest execution failed. Please try again later."
        )
        set_request_lang("zh-CN")
        assert t("common.opFailed", op="回测执行") == "回测执行执行失败，请稍后重试"


class TestVmsg:
    """vmsg() 在消息产出点的行为（zh 逐字不变）。"""

    def test_chinese_template_in_zh(self):
        set_request_lang("zh-CN")
        assert vmsg("validator.codeEmpty", "股票代码不能为空") == "股票代码不能为空"

    def test_english_catalog_in_en(self):
        set_request_lang("en-US")
        assert vmsg("validator.codeEmpty", "股票代码不能为空") == "Stock code cannot be empty"

    def test_params_zh_and_en(self):
        set_request_lang("zh-CN")
        assert vmsg("validator.codeInvalid", "股票代码 {code} 不是有效的A股代码",
                    code="123456") == "股票代码 123456 不是有效的A股代码"
        set_request_lang("en-US")
        assert vmsg("validator.codeInvalid", "股票代码 {code} 不是有效的A股代码",
                    code="123456") == "Stock code 123456 is not a valid A-share code"

    def test_unknown_key_keeps_chinese_template(self):
        set_request_lang("en-US")
        assert vmsg("test.unknown", "中文模板 {x}", x=1) == "中文模板 1"


class TestTrError:
    """tr_error() 的精确/参数化匹配。"""

    def test_zh_language_is_passthrough(self):
        set_request_lang("zh-CN")
        assert tr_error("策略不存在") == "策略不存在"

    def test_exact_match(self):
        set_request_lang("en-US")
        assert tr_error("策略不存在") == "Strategy not found"

    def test_template_match(self):
        set_request_lang("en-US")
        assert tr_error("策略 我的策略 不存在或不是用户策略") == (
            "Strategy 我的策略 does not exist or is not a user strategy"
        )
        assert tr_error("模板 sentiment_ma 不存在") == "Template sentiment_ma does not exist"

    def test_unknown_message_passthrough(self):
        set_request_lang("en-US")
        assert tr_error("某个未收录的中文错误") == "某个未收录的中文错误"
        assert tr_error("already english") == "already english"
        assert tr_error("") == ""


class TestSetRequestLang:
    """语言归一与写入。"""

    @pytest.mark.parametrize("raw,expected", [
        ("zh-CN", "zh-CN"),
        ("zh", "zh-CN"),
        ("zh_cn", "zh-CN"),
        ("en-US", "en-US"),
        ("EN-us", "en-US"),
        ("en", "en-US"),
        ("fr-FR", DEFAULT_LANG),
        ("", DEFAULT_LANG),
        (None, DEFAULT_LANG),
        (123, DEFAULT_LANG),
    ])
    def test_normalize(self, raw, expected):
        assert normalize_lang(raw) == expected
        assert expected in SUPPORTED_LANGS

    def test_set_returns_resolved_and_updates_context(self):
        assert set_request_lang("en") == "en-US"
        assert get_lang() == "en-US"
        assert set_request_lang("bogus") == DEFAULT_LANG
        assert get_lang() == DEFAULT_LANG

    def test_js_bundle_only_js_keys(self):
        set_request_lang("en-US")
        bundle = i18n_js_bundle()
        assert bundle
        assert all(k.startswith("js.") for k in bundle)
        assert bundle["js.loading"] == "Loading..."
        set_request_lang("zh-CN")
        assert i18n_js_bundle()["js.loading"] == "加载中..."


# ---------------------------------------------------------------------------
# 中间件与 /set-lang 路由（真实 FastAPI 应用）
# ---------------------------------------------------------------------------
class TestLanguageMiddleware:
    """cookie → ContextVar，且能传播到线程池端点。"""

    def test_default_is_chinese(self, client):
        assert client.get("/__i18n_probe").json() == {"lang": "zh-CN"}

    def test_cookie_sets_english(self, client):
        resp = client.get("/__i18n_probe", cookies={LANG_COOKIE: "en-US"})
        assert resp.json() == {"lang": "en-US"}

    def test_cookie_alias_and_unknown(self, client):
        assert client.get("/__i18n_probe", cookies={LANG_COOKIE: "en"}).json()["lang"] == "en-US"
        assert client.get("/__i18n_probe", cookies={LANG_COOKIE: "klingon"}).json()["lang"] == "zh-CN"

    def test_threadpool_endpoint_receives_lang(self, client):
        resp = client.get("/__i18n_probe_threadpool", cookies={LANG_COOKIE: "en-US"})
        assert resp.json() == {"lang": "en-US"}


class TestSetLangRoute:
    """语言切换路由：cookie 写入与开放重定向防护。"""

    def test_sets_cookie_and_redirects(self, client):
        resp = client.get("/set-lang?lang=en-US&next=/strategies", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "/strategies"
        cookie = resp.headers["set-cookie"]
        assert f"{LANG_COOKIE}=en-US" in cookie
        assert "Path=/" in cookie
        assert "HttpOnly" not in cookie and "httponly" not in cookie.lower()

    def test_invalid_lang_falls_back_to_default(self, client):
        resp = client.get("/set-lang?lang=klingon&next=/", follow_redirects=False)
        assert f"{LANG_COOKIE}={DEFAULT_LANG}" in resp.headers["set-cookie"]

    def test_unknown_empty_next_defaults_to_root(self, client):
        assert client.get("/set-lang?lang=en-US", follow_redirects=False).headers["location"] == "/"
        assert client.get("/set-lang?lang=en-US&next=", follow_redirects=False).headers["location"] == "/"

    @pytest.mark.parametrize("bad_next", [
        "//evil.example.com",
        "//evil.example.com/x",
        "https://evil.example.com",
        "http://evil.example.com/path",
        r"/\evil.example.com",
        "javascript:alert(1)",
    ])
    def test_open_redirect_rejected(self, client, bad_next):
        resp = client.get(f"/set-lang?lang=en-US&next={bad_next}", follow_redirects=False)
        assert resp.headers["location"] == "/"

    def test_internal_next_preserved(self, client):
        resp = client.get("/set-lang?lang=zh-CN&next=/backtest?market=us", follow_redirects=False)
        assert resp.headers["location"] == "/backtest?market=us"

    def test_cookie_takes_effect_on_next_request(self, client):
        client.get("/set-lang?lang=en-US&next=/", follow_redirects=False)
        assert client.get("/__i18n_probe").json()["lang"] == "en-US"


# ---------------------------------------------------------------------------
# 模板接线
# ---------------------------------------------------------------------------
class TestTemplateWiring:
    """首页渲染：语言切换真正改变界面文案。"""

    def test_home_zh(self, client):
        html = client.get("/", cookies={LANG_COOKIE: "zh-CN"}).text
        assert '<html lang="zh-CN">' in html
        assert "首页" in html
        assert "让量化投资更简单" in html
        assert "加载中..." in html
        assert "window.__I18N__" in html

    def test_home_en(self, client):
        html = client.get("/", cookies={LANG_COOKIE: "en-US"}).text
        assert '<html lang="en-US">' in html
        assert "Welcome to EmoQunt Quant System" in html
        assert "Making quantitative investing simpler" in html
        assert "Loading..." in html
        assert '"js.loading": "Loading..."' in html
        assert "让量化投资更简单" not in html
        assert "首页" not in html

    def test_language_toggle_points_to_other_language(self, client):
        zh_html = client.get("/backtest", cookies={LANG_COOKIE: "zh-CN"}).text
        assert "lang=en-US&amp;next=/backtest" in zh_html
        en_html = client.get("/backtest", cookies={LANG_COOKIE: "en-US"}).text
        assert "lang=zh-CN&amp;next=/backtest" in en_html

    def test_error_page_translated(self, client):
        # 非法参数触发 HTML 错误页（校验消息由 validators 的 vmsg 产出，走线程池 def 路由）
        resp = client.post(
            "/analyze_sentiment",
            data={"strategy": "a", "stock_code": "600000"},
            cookies={LANG_COOKIE: "en-US"},
        )
        assert resp.status_code == 200
        assert "Something went wrong" in resp.text
        assert "Strategy name must be at least 2 characters long" in resp.text

    def test_error_page_chinese_unchanged(self, client):
        resp = client.post(
            "/analyze_sentiment",
            data={"strategy": "a", "stock_code": "600000"},
            cookies={LANG_COOKIE: "zh-CN"},
        )
        assert resp.status_code == 200
        assert "发生错误" in resp.text
        assert "策略名称长度不能少于2个字符" in resp.text


class TestApiErrorBoundary:
    """JSON 出口的 tr_error：文案翻译不改变状态码判定。"""

    def test_404_detail_translated(self, client):
        resp = client.get("/api/strategies/detail/nosuchstrategy", cookies={LANG_COOKIE: "en-US"})
        assert resp.status_code == 404
        assert resp.json() == {"error": "Strategy not found"}

    def test_403_routing_uses_original_chinese(self, client):
        """`403 if "不存在" in result["error"]` 在 en 下仍须命中（判定先于翻译）。"""
        resp = client.put(
            "/api/strategies/nosuchstrategy",
            json={"description": "", "parameters": [], "template": "sentiment_ma"},
            cookies={LANG_COOKIE: "en-US"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == (
            "Strategy nosuchstrategy does not exist or is not a user strategy"
        )

    def test_403_routing_chinese_unchanged(self, client):
        resp = client.put(
            "/api/strategies/nosuchstrategy",
            json={"description": "", "parameters": [], "template": "sentiment_ma"},
            cookies={LANG_COOKIE: "zh-CN"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "策略 nosuchstrategy 不存在或不是用户策略"

    def test_validation_error_translated(self, client):
        resp = client.get("/api/kline?stock_code=12345", cookies={LANG_COOKIE: "en-US"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid stock code 12345: expected 6 digits"


# ---------------------------------------------------------------------------
# 目录完整性
# ---------------------------------------------------------------------------
class TestCatalogIntegrity:
    """目录条目形状与跨模块契约。"""

    def test_every_entry_has_zh_and_en(self):
        missing = [k for k, v in MESSAGES.items() if not v.get("zh") or not v.get("en")]
        assert missing == []

    def test_metric_keys_match_metric_name(self):
        """metric.<中文指标名> 的键段必须等于中文指标名本身。"""
        for key, entry in MESSAGES.items():
            if key.startswith("metric."):
                assert entry["zh"] == key[len("metric."):]

    def test_metric_en_titles(self):
        set_request_lang("en-US")
        assert t("metric.总收益率", "总收益率") == "Total Return"
        assert t("metric.最大回撤", "最大回撤") == "Max Drawdown"
        # 未收录的指标键由 default 兜底，不会出现空标签
        assert t("metric.未收录指标", "未收录指标") == "未收录指标"

    def test_metric_keys_cover_backtest_result_response(self):
        """run_backtest_with_charts 在 zh 下产出的指标键必须都有 en 标签。"""
        expected = {
            "总收益率", "年化收益率", "夏普比率", "最大回撤", "胜率", "盈亏比", "信息比率",
            "年化波动率", "卡玛比率", "下行标准差", "交易次数", "盈利交易数", "亏损交易数",
            "平均盈利", "平均亏损", "最大回撤开始时间", "最大回撤结束时间",
        }
        missing = [k for k in expected if f"metric.{k}" not in MESSAGES]
        assert missing == []

    def test_setup_checks_have_ids_and_catalog_names(self):
        """system.py 每个自检项的 ASCII id 都要有 name 条目（供 setup.html 渲染）。"""
        from src.services.system import get_setup_status

        status = get_setup_status(include_caches=False)
        assert status["checks"]
        for check in status["checks"]:
            cid = check["id"]
            assert re.match(r"^[a-z][a-z0-9_]*$", cid), check
            assert f"setup.check.{cid}.name" in MESSAGES, cid
            # detail/hint 按状态分键（部分状态为动态文案，不强制每条都收录）
            assert any(k.startswith(f"setup.check.{cid}.") for k in MESSAGES), cid

    def test_setup_names_have_en(self):
        set_request_lang("en-US")
        assert t("setup.check.python.name", "Python 版本") == "Python version"
        assert t("setup.check.env_file.name", ".env 配置文件") == ".env configuration file"

    def test_validator_messages_stay_identical_in_zh(self):
        """zh 校验消息必须与改造前的 f-string 逐字一致（回归护栏）。"""
        from src.utils.validators import (
            validate_commission_rate,
            validate_date,
            validate_date_range,
            validate_initial_capital,
            validate_stock_code,
            validate_strategy_name,
        )

        set_request_lang("zh-CN")
        assert validate_stock_code("") == (False, "股票代码不能为空")
        assert validate_stock_code("12345") == (False, "股票代码格式错误: 12345，应为6位数字")
        assert validate_stock_code("123456") == (False, "股票代码 123456 不是有效的A股代码")
        assert validate_date("", date_name="开始日期") == (False, "开始日期不能为空")
        assert validate_date_range("2024-01-01", "2024-01-15") == (False, "回测时间跨度不能少于30天")
        assert validate_initial_capital("x")[1] == "初始资金必须是数字"
        assert validate_commission_rate(0.2)[1] == "佣金费率不能超过 10.0%"
        assert validate_strategy_name("a")[1] == "策略名称长度不能少于2个字符"

    def test_validator_messages_english(self):
        from src.utils.validators import validate_date, validate_stock_code

        set_request_lang("en-US")
        assert validate_stock_code("") == (False, "Stock code cannot be empty")
        assert validate_date("", date_name="开始日期") == (False, "start date cannot be empty")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
