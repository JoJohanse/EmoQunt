"""
系统自检与安装引导服务

为「初次安装引导」提供数据（/setup 页面、/api/system/setup-status、
`python web_app.py --check-env` 命令行自检）。

设计约束：
- 只做本地快速检查（文件存在性、环境变量、短超时连接探测），不做网络抓取，
  保证 /setup 页面与首页横幅检查即时返回；
- 每个检查项 status ∈ {ok, warn, fail, skip}：
  - ok   正常
  - warn 功能降级可用（不阻断核心回测，但建议处理）
  - fail 核心功能不可用，必须处理
  - skip 用户显式关闭的可选项（如 QDT_DB_CACHE_ENABLED=false）
- 每个检查项附带 hint（修复建议）与 detail（当前值），供引导页直接渲染。
"""

import sys
from datetime import datetime
from pathlib import Path

from src.utils.env import get_env
from src.utils.paths import (
    PROJECT_ROOT, get_frontend_dist_dir, get_logs_dir, get_output_dir, ensure_dir,
)

# .env.example 中的占位值——用户只是复制了模板还没填
_PLACEHOLDER_VALUES = {"your-api-key-here", ""}

# 触发「未完成安装引导」提示的 warn 项（fail 项始终触发）
_BANNER_WARN_IDS = {"llm_api_key", "frontend_dist"}


def _check_python() -> dict:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 11)
    return {
        "id": "python", "label": "Python 版本", "status": "ok" if ok else "fail",
        "detail": version, "hint": "需要 Python 3.11+（推荐 conda 环境 qdt）",
    }


def _check_env_file() -> dict:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        return {
            "id": "env_file", "label": ".env 配置文件", "status": "ok",
            "detail": str(env_path), "hint": "",
        }
    return {
        "id": "env_file", "label": ".env 配置文件", "status": "fail",
        "detail": "未找到 .env", "hint": "复制模板：copy .env.example .env（Linux/Mac: cp .env.example .env），再填入 API_KEY 等真实值",
    }


def _check_llm_api_key() -> dict:
    api_key = (get_env("API_KEY") or "").strip()
    if api_key and api_key.lower() not in _PLACEHOLDER_VALUES:
        return {
            "id": "llm_api_key", "label": "LLM API Key（舆情分析）", "status": "ok",
            "detail": "已配置", "hint": "",
        }
    return {
        "id": "llm_api_key", "label": "LLM API Key（舆情分析）", "status": "warn",
        "detail": "未配置或仍为占位值", "hint": "在 .env 中设置 API_KEY / LLM_BASE_URL / LLM_MODEL（OpenAI 兼容接口）；不配置则舆情分析不可用，回测功能不受影响",
    }


def _check_agent_api_key() -> dict:
    agent_key = (get_env("AGENT_API_KEY") or "").strip()
    fallback_key = (get_env("API_KEY") or "").strip()
    if (agent_key and agent_key.lower() not in _PLACEHOLDER_VALUES) or (
            fallback_key and fallback_key.lower() not in _PLACEHOLDER_VALUES):
        return {
            "id": "agent_api_key", "label": "AI 助手 Key", "status": "ok",
            "detail": "AGENT_API_KEY 或回退 API_KEY 已配置", "hint": "",
        }
    return {
        "id": "agent_api_key", "label": "AI 助手 Key", "status": "warn",
        "detail": "未配置", "hint": "AI 投资助手需要 AGENT_API_KEY（留空则回退 API_KEY）",
    }


def _check_tushare_token() -> dict:
    token = (get_env("TUSHARE_TOKEN") or "").strip()
    if token:
        return {
            "id": "tushare_token", "label": "Tushare Pro Token", "status": "ok",
            "detail": "已配置（A 股数据主源）", "hint": "",
        }
    return {
        "id": "tushare_token", "label": "Tushare Pro Token", "status": "skip",
        "detail": "可选，未配置", "hint": "注册 tushare.pro 获取 token 后在 .env 中设置 TUSHARE_TOKEN，A 股数据链升级为 Tushare → akshare → baostock；不配置则免费源完全可用",
    }


def _check_frontend_dist() -> dict:
    index_html = get_frontend_dist_dir() / "index.html"
    if index_html.exists():
        return {
            "id": "frontend_dist", "label": "Vue3 SPA 构建产物", "status": "ok",
            "detail": str(get_frontend_dist_dir()), "hint": "",
        }
    return {
        "id": "frontend_dist", "label": "Vue3 SPA 构建产物", "status": "warn",
        "detail": "frontend/dist 未构建", "hint": "在 frontend/ 目录执行 npm install && npm run build；不构建则 /spa/* 返回 503，Jinja2 前端（/）不受影响",
    }


def _check_sentiment_snapshots() -> dict:
    snapshot_dir = PROJECT_ROOT / "nes_data" / "sentiment_results"
    count = len(list(snapshot_dir.glob("*.json"))) if snapshot_dir.is_dir() else 0
    if count > 0:
        return {
            "id": "sentiment_snapshots", "label": "历史情绪快照", "status": "ok",
            "detail": f"{count} 份快照", "hint": "",
        }
    return {
        "id": "sentiment_snapshots", "label": "历史情绪快照", "status": "warn",
        "detail": "nes_data/sentiment_results/ 为空", "hint": "运行一次舆情分析可生成快照；没有快照时情绪过滤策略退化为普通均线策略",
    }


def _check_dirs_writable() -> dict:
    problems = []
    for name, path in [("logs", get_logs_dir()), ("output", get_output_dir())]:
        try:
            ensure_dir(path)
            probe = Path(path) / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            problems.append(f"{name}({e})")
    if problems:
        return {
            "id": "dirs_writable", "label": "运行目录可写", "status": "fail",
            "detail": "；".join(problems), "hint": "检查目录权限：logs/ 与 output/ 必须可写（图表与日志输出）",
        }
    return {
        "id": "dirs_writable", "label": "运行目录可写", "status": "ok",
        "detail": "logs/、output/ 均可写", "hint": "",
    }


def _check_caches() -> list:
    """数据缓存层（PostgreSQL + Redis）：连不上只降级（warn），不阻断。"""
    checks = []
    try:
        from src.data import db as _db
        health = _db.healthcheck()
    except Exception as e:  # 数据缓存层模块异常不影响主流程
        err = str(e)
        for cid, label in [("pg_cache", "PostgreSQL 缓存"), ("redis_cache", "Redis 热缓存")]:
            checks.append({
                "id": cid, "label": label, "status": "warn",
                "detail": f"检查失败：{err[:80]}", "hint": "docker compose up -d 可启动本地缓存",
            })
        return checks
    pg_enabled = getattr(_db, "DB_CACHE_ENABLED", True)
    redis_enabled = getattr(_db, "REDIS_CACHE_ENABLED", True)
    checks.append({
        "id": "pg_cache", "label": "PostgreSQL 缓存",
        "status": ("ok" if health.get("postgres") else "warn") if pg_enabled else "skip",
        "detail": "已连接" if health.get("postgres") else ("未启用（QDT_DB_CACHE_ENABLED=false）" if not pg_enabled else "未连接"),
        "hint": "" if health.get("postgres") else
                ("已显式关闭" if not pg_enabled else "可选：docker compose up -d 启动后自动接入；未启动时自动降级到 CSV + 网络数据源"),
    })
    checks.append({
        "id": "redis_cache", "label": "Redis 热缓存",
        "status": ("ok" if health.get("redis") else "warn") if redis_enabled else "skip",
        "detail": "已连接" if health.get("redis") else ("未启用（QDT_REDIS_CACHE_ENABLED=false）" if not redis_enabled else "未连接"),
        "hint": "" if health.get("redis") else
                ("已显式关闭" if not redis_enabled else "可选：docker compose up -d 启动后自动接入；未启动时自动降级"),
    })
    return checks


def get_setup_status(include_caches: bool = True) -> dict:
    """
    汇总安装自检结果。

    :param include_caches: 是否探测 PostgreSQL/Redis 缓存层（涉及短超时连接，
                           首页横幅等高频路径应传 False 只做本地检查）
    :return: {"checks": [...], "needs_setup": bool, "generated_at": str}
    """
    checks = [
        _check_python(),
        _check_env_file(),
        _check_llm_api_key(),
        _check_agent_api_key(),
        _check_tushare_token(),
        _check_frontend_dist(),
        _check_sentiment_snapshots(),
        _check_dirs_writable(),
    ]
    if include_caches:
        checks.extend(_check_caches())
    has_fail = any(c["status"] == "fail" for c in checks)
    has_banner_warn = any(c["status"] == "warn" and c["id"] in _BANNER_WARN_IDS for c in checks)
    return {
        "checks": checks,
        "needs_setup": has_fail or has_banner_warn,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def needs_setup_guide() -> bool:
    """
    首页横幅用的轻量判断：是否处于「初次使用未完成配置」状态。

    只做文件/环境变量读取（微秒级），供每个首页请求调用；
    完整自检（含缓存探测）请用 get_setup_status()。
    """
    env_ok = (PROJECT_ROOT / ".env").exists()
    api_key = (get_env("API_KEY") or "").strip().lower()
    api_ok = api_key and api_key not in _PLACEHOLDER_VALUES
    return not (env_ok and api_ok)


_STATUS_MARKS = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]", "skip": "[SKIP]"}


def run_setup_check_cli() -> int:
    """
    命令行自检入口（python web_app.py --check-env）。

    :return: 进程退出码——存在 fail 项返回 1，否则 0
    """
    status = get_setup_status(include_caches=True)
    print("EmoQunt 安装自检")
    print("=" * 62)
    for c in status["checks"]:
        mark = _STATUS_MARKS.get(c["status"], "[?]   ")
        print(f"{mark} {c['label']}: {c['detail']}")
        if c["hint"] and c["status"] in ("warn", "fail"):
            print(f"         └ 修复建议: {c['hint']}")
    print("=" * 62)
    fails = [c for c in status["checks"] if c["status"] == "fail"]
    warns = [c for c in status["checks"] if c["status"] == "warn"]
    if fails:
        print(f"结果：{len(fails)} 项失败、{len(warns)} 项警告——请先处理失败项再启动服务")
        return 1
    print(f"结果：无失败项，{len(warns)} 项可选警告（详见 /setup 安装引导页）")
    return 0
