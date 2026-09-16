"""
国际化（i18n）引擎

为三个消费面提供统一的中英文案解析：
    - Jinja2 模板：全局函数 ``t(key, default=None, **params)``（配套 ``lang()``
      与 ``i18n_js()``，在 web_app.py 中注册到 ``templates.env.globals``）；
    - 后端服务/校验器（消息产出点）：``vmsg(key, zh_template, **params)``——
      zh 模板逐字不变，en 命中目录时换成英译模板；
    - HTTP 边界（无法改成 vmsg 的中文字面量）：``tr_error(msg)`` 按
      ``i18n_data/errors.py`` 的中文原文映射输出英文。

语言取值来自 ``emoqunt_lang`` cookie，由 web_app.py 的 HTTP 中间件写入
``_current_lang`` ContextVar；ContextVar 随「中间件 → 路由」自动传播（含
线程池 ``def`` 端点与 ``async def`` 端点），无需在路由层重复解析。

文案目录按域拆分在 ``src/utils/i18n_data/`` 包内（``MESSAGE_MODULES`` 为合并
顺序，后者覆盖前者），本模块只做加载与查找，不持有业务文案。目录条目的形状
固定为 ``{"some.key": {"zh": "...", "en": "..."}}``。

注意：本模块与 i18n_data 必须保持「导入轻量」——不得引入 pandas/fastapi 等重依赖，
因为 validators.py 等底层模块会在导入期引用它。
"""
from __future__ import annotations

import importlib
import re
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Pattern, Tuple

from src.utils.i18n_data import MESSAGE_MODULES

# 语言 cookie 名与取值
LANG_COOKIE = "emoqunt_lang"
SUPPORTED_LANGS = ("zh-CN", "en-US")
DEFAULT_LANG = "zh-CN"

# 语言取值 → 目录条目内的短键
_LANG_KEYS = {"zh-CN": "zh", "en-US": "en"}

# 语言别名（大小写不敏感）：未知取值一律回落 DEFAULT_LANG
_LANG_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-hant": "zh-CN",
    "zh-tw": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en_us": "en-US",
    "en-gb": "en-US",
}

# 注入到 window.__I18N__ 的键前缀（前端内联脚本用 tt() 消费）
JS_KEY_PREFIX = "js."

# 当前请求语言（中间件写入；无请求上下文时为 DEFAULT_LANG）
_current_lang: ContextVar[str] = ContextVar("emoqunt_current_lang", default=DEFAULT_LANG)


def normalize_lang(lang: Any) -> str:
    """
    归一语言取值：支持 zh/zh-CN/en/en-US 等别名（大小写不敏感）。

    未知、空值或非字符串一律回落 DEFAULT_LANG。

    :param lang: 原始语言取值（通常来自 cookie 或查询参数）
    :return: SUPPORTED_LANGS 之一
    """
    return _LANG_ALIASES.get(str(lang or "").strip().lower(), DEFAULT_LANG)


def get_lang() -> str:
    """
    读取当前请求语言（ContextVar）。

    :return: SUPPORTED_LANGS 之一
    """
    return _current_lang.get()


def set_request_lang(lang: Any) -> str:
    """
    写入当前请求语言（中间件/测试用），返回归一后的结果。

    :param lang: 原始语言取值
    :return: 写入的归一语言（SUPPORTED_LANGS 之一）
    """
    resolved = normalize_lang(lang)
    _current_lang.set(resolved)
    return resolved


def _load_messages() -> Dict[str, Dict[str, str]]:
    """合并 i18n_data 下所有目录模块的 MESSAGES（后者覆盖同键条目）。"""
    merged: Dict[str, Dict[str, str]] = {}
    for module_name in MESSAGE_MODULES:
        module = importlib.import_module(f"{__package__}.i18n_data.{module_name}")
        for key, entry in getattr(module, "MESSAGES", {}).items():
            merged.setdefault(key, {}).update(entry)
    return merged


# 扁平文案目录：{"some.key": {"zh": "...", "en": "..."}}
MESSAGES: Dict[str, Dict[str, str]] = _load_messages()

# tr_error 专用：中文原文 → 英文（精确匹配）
ERROR_MESSAGES: Dict[str, str] = dict(
    getattr(importlib.import_module(f"{__package__}.i18n_data.errors"), "ERROR_MESSAGES", {})
)

# tr_error 专用：带参数的条目（中文模板 → 英文模板），如 "策略 {name} 不存在"
_ERROR_TEMPLATE_SOURCE: Dict[str, str] = dict(
    getattr(importlib.import_module(f"{__package__}.i18n_data.errors"), "ERROR_TEMPLATES", {})
)


def _build_error_matchers() -> List[Tuple[Pattern[str], List[str], str]]:
    """把中文错误模板编译为 (正则, 占位符名列表, 英译模板) 三元组。"""
    matchers: List[Tuple[Pattern[str], List[str], str]] = []
    for zh_template, en_template in _ERROR_TEMPLATE_SOURCE.items():
        pattern = re.escape(zh_template)
        names: List[str] = []
        for name in re.findall(r"\\\{(\w+)\\\}", pattern):
            names.append(name)
            pattern = pattern.replace(r"\{" + name + r"\}", "(.+?)", 1)
        matchers.append((re.compile("^" + pattern + "$"), names, en_template))
    return matchers


_ERROR_MATCHERS = _build_error_matchers()


def t(key: str, default: Optional[str] = None, **params: Any) -> str:
    """
    解析文案：当前语言 → zh 兜底 → default → key 本身。

    :param key: 目录键（如 ``nav.home`` / ``metric.总收益率``）
    :param default: 目录缺失时的兜底文案（可为中文原文，为 None 时兜底为 key）
    :param params: ``{name}`` 形式的插值参数（str.format）
    :return: 解析后的文案
    """
    entry = MESSAGES.get(key)
    text = None
    if entry:
        text = entry.get(_LANG_KEYS.get(get_lang(), "zh")) or entry.get("zh")
    if not text:
        text = default if default is not None else key
    return text.format(**params) if params else text


def vmsg(key: str, zh_template: str, **params: Any) -> str:
    """
    消息产出点的翻译助手（校验器/服务层用）。

    当前语言为 en 且目录命中时用英译模板，否则一律用调用方传入的中文模板——
    因此 zh 体验与改造前逐字一致。

    :param key: 目录键（如 ``validator.stockCodeEmpty``）
    :param zh_template: 中文模板原文（含 ``{param}`` 占位符）
    :param params: 插值参数
    :return: 本地化后的消息
    """
    template = zh_template
    if get_lang() == "en-US":
        entry = MESSAGES.get(key)
        if entry and entry.get("en"):
            template = entry["en"]
    return template.format(**params) if params else template


def tr_error(msg: str) -> str:
    """
    HTTP 边界的错误文案翻译：中文原文 → 英文（zh 语言下原样返回）。

    精确匹配 ``ERROR_MESSAGES``；未命中再尝试 ``ERROR_TEMPLATES`` 的参数化
    匹配（如 ``策略 {name} 不存在或不是用户策略``）；都不命中则原样返回。
    调用时机必须在「状态码判定之后」——web_app.py 的 ``403 if "不存在" in ...``
    之类的中文子串判定仍依赖服务层返回的原始中文。

    :param msg: 服务层/路由层产出的错误文案
    :return: 英文译文或原样文案
    """
    if not msg or get_lang() != "en-US":
        return msg
    exact = ERROR_MESSAGES.get(msg)
    if exact is not None:
        return exact
    for pattern, names, en_template in _ERROR_MATCHERS:
        matched = pattern.match(msg)
        if matched:
            return en_template.format(**dict(zip(names, matched.groups())))
    return msg


def i18n_js_bundle() -> Dict[str, str]:
    """
    收集 ``js.`` 前缀的文案（当前语言），供模板注入 ``window.__I18N__``。

    模板侧用 ``tt('js.xxx', '中文兜底')`` 消费，见 base.html。

    :return: {key: 当前语言文案}
    """
    lang_key = _LANG_KEYS.get(get_lang(), "zh")
    return {
        key: (entry.get(lang_key) or entry.get("zh") or key)
        for key, entry in MESSAGES.items()
        if key.startswith(JS_KEY_PREFIX)
    }
