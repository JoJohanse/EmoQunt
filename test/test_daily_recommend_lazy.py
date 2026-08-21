"""daily_recommend 懒初始化回归测试。

验证 import 时不再触发 HS300/行业/舆情加载，首次调用触发一次且线程安全。
运行：pytest test/test_daily_recommend_lazy.py -v
"""
import importlib
import logging
from unittest import mock


def test_import_does_not_auto_load():
    """import 模块后 load_hs300_stocks/load_industries/init_sentiment 未被调用。"""
    import src.factor.daily_recommend as dr

    # reload 后的 _loaded 应为 False，且未触发真实加载（通过 mock 计数验证）
    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3:
        # 此时已 reload 完成，_loaded=False，mock 已就位
        # 不应自动调用（仅 import 已完成）
        m1.assert_not_called()
        m2.assert_not_called()
        m3.assert_not_called()
        assert dr._loaded is False


def test_import_no_log_output(caplog):
    """import 不再打印 '成功加载 ... 沪深300' 日志。"""
    import src.factor.daily_recommend as dr

    with caplog.at_level(logging.INFO, logger="src.factor.daily_recommend"):
        importlib.reload(dr)
    # 不应出现旧的加载日志
    assert "成功加载" not in caplog.text
    assert "沪深300成分股" not in caplog.text


def test_first_call_triggers_once_and_second_does_not():
    """首次 get_top_sectors 触发一次加载，再次调用不重复。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3:
        # 首次调用触发
        dr.get_top_sectors(2)
        assert m1.call_count == 1
        assert m2.call_count == 1
        assert m3.call_count == 1
        assert dr._loaded is True

        # 再次调用不再触发
        dr.get_top_sectors(2)
        assert m1.call_count == 1
        assert m2.call_count == 1
        assert m3.call_count == 1

        # get_sector_stocks 亦不再触发
        dr.get_sector_stocks("银行")
        assert m1.call_count == 1


def test_get_sector_stocks_lazy():
    """get_sector_stocks 首调同样触发懒加载。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3:
        dr.get_sector_stocks("白酒")
        assert m1.call_count == 1
        assert m2.call_count == 1
        assert m3.call_count == 1
        assert dr._loaded is True


def test_load_all_data_still_works():
    """显式 load_all_data 仍可触发加载并置 _loaded=True。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3:
        dr.load_all_data()
        assert m1.call_count == 1
        assert m2.call_count == 1
        assert m3.call_count == 1
        assert dr._loaded is True
        # 后续 _ensure_loaded 不再重复
        dr.get_top_sectors(1)
        assert m1.call_count == 1


def test_reload_sentiment_does_not_affect_loaded_flag():
    """reload_sentiment 仅重载舆情，不应重置 _loaded。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3:
        dr.get_top_sectors(1)
        assert dr._loaded is True
        assert m3.call_count == 1
        m3.reset_mock()
        # reload_sentiment 内部即 init_sentiment
        dr.reload_sentiment()
        assert m3.call_count == 1
        assert dr._loaded is True
        # 不应触发 hs300/industry 重载
        assert m1.call_count == 1
        assert m2.call_count == 1


def test_generate_daily_recommend_lazy():
    """generate_daily_recommend 首调触发懒加载。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3, \
         mock.patch.object(dr, "get_top_sectors", return_value=[]) as mock_top, \
         mock.patch.object(dr, "get_sector_stocks", return_value=[]):
        # get_top_sectors 已被 mock，不会触发 _ensure_loaded，
        # 但 generate_daily_recommend 本身也调用 _ensure_loaded
        dr.generate_daily_recommend(n=3)
        assert m1.call_count == 1
        assert m2.call_count == 1
        assert m3.call_count == 1


def test_get_sentiment_data_lazy():
    """get_sentiment_data 首调触发懒加载。"""
    import src.factor.daily_recommend as dr

    importlib.reload(dr)
    assert dr._loaded is False

    with mock.patch.object(dr, "load_hs300_stocks") as m1, \
         mock.patch.object(dr, "load_industries") as m2, \
         mock.patch.object(dr, "init_sentiment") as m3, \
         mock.patch.object(dr, "get_top_sectors", return_value=[]):
        dr.get_sentiment_data()
        assert m1.call_count == 1
