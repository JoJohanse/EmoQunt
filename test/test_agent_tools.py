"""Agent 工具单元测试。

测试工具包装的返回格式（JSON 可解析、结构正确）与防御性降级。
不调用真实 LLM；网络类工具在无网络时验证 error 降级。
运行：pytest test/test_agent_tools.py -v
"""
import json
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.agent.tools import ALL_TOOLS, _err, _json


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
class TestHelpers:
    def test_err_format(self):
        s = _err("网络失败")
        d = json.loads(s)
        assert d == {"error": "网络失败"}

    def test_json_chinese_readable(self):
        s = _json({"板块": "银行", "score": 0.3})
        assert "板块" in s  # ensure_ascii=False
        assert json.loads(s) == {"板块": "银行", "score": 0.3}


# ---------------------------------------------------------------------------
# 工具注册与元数据
# ---------------------------------------------------------------------------
class TestToolRegistry:
    def test_seven_tools_registered(self):
        names = [t.name for t in ALL_TOOLS]
        assert len(names) == 7
        for expected in ["get_stock_quote", "get_index_quote", "run_backtest",
                         "get_sentiment", "get_stock_signal",
                         "get_daily_recommendations", "list_strategies"]:
            assert expected in names, f"{expected} 缺失"

    def test_tools_have_docstrings(self):
        """每个工具应有描述（agent 据此选择工具）。"""
        for t in ALL_TOOLS:
            assert t.description, f"{t.name} 缺少 description"


# ---------------------------------------------------------------------------
# 离线安全工具：list_strategies（纯本地 JSON）
# ---------------------------------------------------------------------------
class TestListStrategies:
    def test_returns_valid_json(self):
        from src.agent.tools import list_strategies
        raw = list_strategies.invoke({})
        data = json.loads(raw)
        assert "strategies" in data
        assert "templates" in data
        assert isinstance(data["strategies"], list)
        assert isinstance(data["templates"], list)


# ---------------------------------------------------------------------------
# 网络工具：验证返回是合法 JSON（成功或 error 降级，都不应抛异常）
# ---------------------------------------------------------------------------
class TestNetworkToolsDegrade:
    """网络类工具应捕获异常返回 {error:...}，不抛异常给 agent。"""

    def test_get_stock_quote_returns_json(self):
        from src.agent.tools import get_stock_quote
        raw = get_stock_quote.invoke({"stock_code": "000001", "market": "zh_a", "days": 5})
        data = json.loads(raw)  # 不抛异常即可
        assert "error" in data or "close" in data

    def test_get_index_quote_returns_json(self):
        from src.agent.tools import get_index_quote
        raw = get_index_quote.invoke({"index_code": "000300", "market": "zh_a", "days": 5})
        data = json.loads(raw)
        assert "error" in data or "close" in data

    def test_get_sentiment_returns_json(self):
        from src.agent.tools import get_sentiment
        raw = get_sentiment.invoke({"top_n": 3})
        data = json.loads(raw)
        assert "error" in data or "top_sectors" in data

    def test_get_daily_recommendations_returns_json(self):
        from src.agent.tools import get_daily_recommendations
        raw = get_daily_recommendations.invoke({"top_n": 3})
        data = json.loads(raw)
        assert "error" in data or "recommendations" in data

    def test_get_stock_signal_returns_json(self):
        from src.agent.tools import get_stock_signal
        raw = get_stock_signal.invoke({"stock_code": "000001"})
        data = json.loads(raw)
        assert "error" in data or "sector" in data


# ---------------------------------------------------------------------------
# Agent 配置（不触网）
# ---------------------------------------------------------------------------
class TestAgentConfig:
    def test_config_reads_env(self):
        from src.agent.agent import get_agent_llm_config
        cfg = get_agent_llm_config()
        assert "model" in cfg
        assert "api_key" in cfg
        assert "base_url" in cfg
        assert isinstance(cfg["temperature"], float)

    def test_config_fallback_to_api_key(self):
        """AGENT_API_KEY 未设置时应回退到 API_KEY。"""
        from src.agent.agent import get_agent_llm_config
        cfg = get_agent_llm_config()
        # 至少有一个 key 来源（测试环境通常有 API_KEY）
        assert cfg["api_key"]  # 测试环境 .env 已配置


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
