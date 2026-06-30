# coding=utf-8
"""路径工具模块 (src/utils/paths.py) 单元测试。

覆盖：
- PROJECT_ROOT 正确指向项目根
- 各 get_*_dir 辅助函数返回项目根下的预期子目录
- ensure_dir 递归创建目录且幂等
- as_posix 将平台分隔符转换为正斜杠

运行：pytest test/test_utils_paths.py -v
"""
import os
import sys
from pathlib import Path

import pytest

# 确保项目根在 sys.path（从 test/ 目录直接 pytest 时也生效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.utils.paths import (
    PROJECT_ROOT,
    ensure_dir,
    get_stock_data_dir,
    get_logs_dir,
    get_output_dir,
    get_config_dir,
    get_sentiment_save_dir,
    get_trendradar_dir,
    get_user_strategies_dir,
    get_web_dir,
    get_frontend_dist_dir,
    as_posix,
)


class TestProjectRoot:
    """项目根目录定位测试。"""

    def test_project_root_is_directory(self):
        assert PROJECT_ROOT.is_dir()

    def test_project_root_contains_src(self):
        # 项目根下应包含 src 与 web_app.py
        assert (PROJECT_ROOT / "src").is_dir()
        assert (PROJECT_ROOT / "web_app.py").is_file()


class TestDirHelpers:
    """各目录辅助函数均应位于项目根下。"""

    @pytest.mark.parametrize("market", ["zh_a", "us"])
    def test_stock_data_dir(self, market):
        d = get_stock_data_dir(market)
        assert d == PROJECT_ROOT / "stock_data" / market

    def test_default_market_is_zh_a(self):
        # 不传参时默认 zh_a
        assert get_stock_data_dir() == PROJECT_ROOT / "stock_data" / "zh_a"

    def test_logs_dir(self):
        assert get_logs_dir() == PROJECT_ROOT / "logs"

    def test_output_dir(self):
        assert get_output_dir() == PROJECT_ROOT / "output"

    def test_config_dir(self):
        assert get_config_dir() == PROJECT_ROOT / "config"
        assert (get_config_dir() / "config.yaml").is_file()

    def test_sentiment_save_dir(self):
        assert get_sentiment_save_dir() == PROJECT_ROOT / "output" / "sentiment_analysis"

    def test_trendradar_dir(self):
        assert get_trendradar_dir() == PROJECT_ROOT / "nes_data" / "trendradar"

    def test_user_strategies_dir(self):
        assert get_user_strategies_dir() == PROJECT_ROOT / "src" / "Strategy" / "user_strategies"

    def test_web_dir(self):
        assert get_web_dir() == PROJECT_ROOT / "web"

    def test_frontend_dist_dir(self):
        assert get_frontend_dist_dir() == PROJECT_ROOT / "frontend" / "dist"


class TestEnsureDir:
    """ensure_dir 行为测试。"""

    def test_creates_nested_dir(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        result = ensure_dir(target)
        assert target.is_dir()
        assert result == Path(target)

    def test_idempotent_on_existing(self, tmp_path):
        target = tmp_path / "exists"
        target.mkdir()
        # 对已存在目录再次调用不应抛异常
        ensure_dir(target)
        assert target.is_dir()

    def test_accepts_string_path(self, tmp_path):
        result = ensure_dir(str(tmp_path / "strpath"))
        assert (tmp_path / "strpath").is_dir()
        assert isinstance(result, Path)


class TestAsPosix:
    """as_posix 路径分隔符转换测试。"""

    def test_converts_os_sep_to_slash(self):
        joined = os.path.join("a", "b", "c")
        assert as_posix(joined) == "a/b/c"

    def test_already_posix(self):
        assert as_posix("a/b/c") == "a/b/c"

    def test_accepts_path_object(self):
        assert as_posix(Path("x") / "y") == "x/y"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
