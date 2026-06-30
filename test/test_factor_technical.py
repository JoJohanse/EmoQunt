# coding=utf-8
"""技术指标计算模块 (src/factor/technical.py) 单元测试。

覆盖 calculate_factor 的日线分支：
- 读取本地 CSV 并计算 MA / RSI / MACD / K 值 / ATR 等指标
- 生成 *_factor.csv 输出文件
- 返回的 DataFrame 包含预期指标列

通过 monkeypatch 将 get_stock_data_dir 重定向到临时目录，使用合成 OHLCV 数据，
不依赖网络或真实股票数据。

运行：pytest test/test_factor_technical.py -v
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import src.factor.technical as tech


def _make_daily_csv(path: str, n: int = 40):
    """生成 n 行合成日线数据（单调上涨收盘价），列名与真实数据一致。"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(10.0, 15.0, n)
    df = pd.DataFrame({
        "时间": dates.strftime("%Y-%m-%d"),
        "开盘": close - 0.1,
        "最高": close + 0.2,
        "最低": close - 0.2,
        "收盘": close,
        "成交量": np.full(n, 1_000_000.0),
        "成交额": close * 1_000_000,
        "流通股数": np.full(n, 1e9),
        "换手率": np.full(n, 0.001),
    })
    df.to_csv(path, index=False, encoding="utf-8")


class TestCalculateFactorDaily:
    """calculate_factor 日线指标计算测试。"""

    @pytest.fixture
    def setup_data_dir(self, tmp_path, monkeypatch):
        """重定向数据目录并在其中放置合成 CSV。"""
        monkeypatch.setattr(tech, "get_stock_data_dir", lambda market="zh_a": tmp_path)
        code, fq, datatype = "000001", "hfq", "daily"
        stock_path = tmp_path / code / fq / datatype
        stock_path.mkdir(parents=True)
        src_csv = stock_path / "000001_hfq_daily_20200101_20241231.csv"
        _make_daily_csv(str(src_csv))
        return code, fq, datatype, stock_path

    def test_returns_expected_indicator_columns(self, setup_data_dir):
        code, fq, datatype, _ = setup_data_dir
        df = tech.calculate_factor(code, datatype=datatype, fq=fq, market="zh_a")
        expected = [
            "时间", "开盘", "最高", "最低", "成交量",
            "ma5(五日均线)", "ma10(十日均线)", "ma20(二十日均线)",
            "rsi(相对强弱指标)", "dif(差离值)", "dea(异同平均数)",
            "macd_hist(柱状图)", "k值", "atr(平均真实价格波幅)",
        ]
        for col in expected:
            assert col in df.columns, f"缺少指标列: {col}"

    def test_indicator_values_finite_on_last_row(self, setup_data_dir):
        code, fq, datatype, _ = setup_data_dir
        df = tech.calculate_factor(code, datatype=datatype, fq=fq, market="zh_a")
        last = df.iloc[-1]
        # 数据足够长，最后一行的各指标应为有限值
        for col in ["ma5(五日均线)", "ma20(二十日均线)", "rsi(相对强弱指标)",
                    "dif(差离值)", "dea(异同平均数)", "macd_hist(柱状图)",
                    "k值", "atr(平均真实价格波幅)"]:
            assert not pd.isna(last[col]), f"最后一行 {col} 不应为 NaN"

    def test_writes_factor_csv(self, setup_data_dir):
        code, fq, datatype, stock_path = setup_data_dir
        tech.calculate_factor(code, datatype=datatype, fq=fq, market="zh_a")
        factor_file = stock_path / f"{code}_{fq}_{datatype}_factor.csv"
        assert factor_file.exists()
        # 输出文件可被重新读取
        out = pd.read_csv(factor_file)
        assert len(out) > 0

    def test_int_stock_code_handled(self, setup_data_dir):
        # 整型代码应被 zfill 为 6 位字符串
        _, fq, datatype, _ = setup_data_dir
        df = tech.calculate_factor(1, datatype=datatype, fq=fq, market="zh_a")
        assert len(df) > 0

    def test_ma5_matches_manual_calc(self, setup_data_dir):
        code, fq, datatype, stock_path = setup_data_dir
        df = tech.calculate_factor(code, datatype=datatype, fq=fq, market="zh_a")
        # 手动验证最后一行 ma5 = 最近 5 日收盘价均值
        src = pd.read_csv(stock_path / "000001_hfq_daily_20200101_20241231.csv")
        expected_ma5 = src["收盘"].tail(5).mean()
        assert df["ma5(五日均线)"].iloc[-1] == pytest.approx(expected_ma5, rel=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
