"""Agent 核心：构建 LangGraph ReAct agent，提供流式与非流式运行接口。

LLM 配置独立于情绪分析：读取 AGENT_* 环境变量（回退到 LLM_* 与 API_KEY）。
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from .prompts import build_system_message
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# 进程级 agent 缓存（避免每次请求重建）
_agent_cache: Optional[Any] = None


def get_agent_llm_config() -> Dict[str, Any]:
    """读取 agent 专用 LLM 配置（AGENT_* 优先，回退到 LLM_* / API_KEY）。

    :return: 含 api_key/model/base_url/temperature/max_tokens/timeout 的字典
    """
    # 延迟导入以触发 .env 加载
    from src.utils.env import get_env, get_env_float, get_env_int

    base_url = get_env("AGENT_BASE_URL", "") or get_env("LLM_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    api_key = get_env("AGENT_API_KEY", "") or get_env("API_KEY", "")
    return {
        "api_key": api_key,
        "model": get_env("AGENT_MODEL", "mimo-v2.5"),
        "base_url": base_url,
        "temperature": get_env_float("AGENT_TEMPERATURE", 0.3),
        "max_tokens": get_env_int("AGENT_MAX_TOKENS", 4096),
        "timeout": get_env_int("AGENT_TIMEOUT", 60),
    }


def _build_llm() -> ChatOpenAI:
    """根据配置构建 ChatOpenAI 实例。"""
    cfg = get_agent_llm_config()
    if not cfg["api_key"]:
        raise RuntimeError(
            "未配置 Agent LLM API Key（请设置 AGENT_API_KEY 或 API_KEY 环境变量）"
        )
    kwargs: Dict[str, Any] = {
        "model": cfg["model"],
        "api_key": cfg["api_key"],
        "base_url": cfg["base_url"],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "timeout": cfg["timeout"],
        "streaming": True,  # 启用流式
    }
    return ChatOpenAI(**kwargs)


def build_agent():
    """构建（并缓存）LangGraph ReAct agent。

    :return: 可调用的 agent（CompiledStateGraph）
    :raises RuntimeError: 若未配置 API Key
    """
    global _agent_cache
    if _agent_cache is not None:
        return _agent_cache
    llm = _build_llm()
    _agent_cache = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=build_system_message(),
    )
    logger.info("Agent 构建完成，模型: %s", get_agent_llm_config()["model"])
    return _agent_cache


def _to_lc_messages(messages: List[Dict]) -> List[BaseMessage]:
    """将前端传入的 {role, content} 列表转为 LangChain 消息对象。

    系统 prompt 由 agent 内部注入，此处忽略 role==system 的消息。
    """
    out: List[BaseMessage] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out


def run_agent(messages: List[Dict]) -> str:
    """非流式运行 agent，返回完整回复文本。

    :param messages: [{role, content}, ...]
    :return: assistant 回复字符串
    """
    agent = build_agent()
    lc_messages = _to_lc_messages(messages)
    result = agent.invoke({"messages": lc_messages})
    # 取最后一条 AI 消息
    ai_msgs = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
    if not ai_msgs:
        return ""
    return ai_msgs[-1].content


async def stream_agent_events(messages: List[Dict]):
    """统一的事件流生成器（深模块）。

    迭代 LangGraph astream_events v2，yield 标准化事件元组：
    - ("token", text)               模型输出 token 增量
    - ("tool", name, args, result)  工具调用
    - ("done",)                     结束
    - ("error", message)            错误

    web_app.py 的 SSE 路由直接消费此生成器；旧的回调式 run_agent_stream 也委托于此。
    """
    agent = build_agent()
    lc_messages = _to_lc_messages(messages)
    tool_args_inflight: Dict[str, str] = {}

    try:
        async for ev in agent.astream_events({"messages": lc_messages}, version="v2"):
            kind = ev.get("event", "")
            nm = ev.get("name", "")

            if kind == "on_chat_model_stream":
                chunk = ev.get("data", {}).get("chunk")
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    yield ("token", text)

            elif kind == "on_tool_start":
                inp = ev.get("data", {}).get("input", "")
                tool_args_inflight[nm] = inp if isinstance(inp, str) else str(inp)

            elif kind == "on_tool_end":
                args = tool_args_inflight.pop(nm, "")
                out = ev.get("data", {}).get("output", "")
                result = out.content if hasattr(out, "content") else str(out)
                yield ("tool", nm, args[:500], result[:800])

        yield ("done",)
    except Exception as e:
        logger.exception("Agent stream_agent_events 失败")
        yield ("error", str(e))


async def run_agent_stream(
    messages: List[Dict],
    on_token: Optional[Callable[[str], None]] = None,
    on_tool: Optional[Callable[[str, str, str], None]] = None,
):
    """流式运行 agent（回调式接口，委托于 stream_agent_events）。

    保留以兼容现有调用者；web_app.py SSE 路由应直接用 stream_agent_events。
    """
    async for evt in stream_agent_events(messages):
        if evt[0] == "token" and on_token:
            on_token(evt[1])
        elif evt[0] == "tool" and on_tool:
            on_tool(evt[1], evt[2], evt[3])
