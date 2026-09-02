"""Thin sync wrapper around MCP client sessions.

Runs ONE persistent event loop in a background thread for the whole app's
lifetime. Every MCP session (Tavily HTTP, PDF stdio) is created once on that
loop and reused. Sync node functions just submit coroutines to it and block
for the result — safe to call from anywhere, no event-loop-per-call bugs.
"""
import asyncio
import atexit
import threading
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from ingestion.config import Config

_sessions: dict[str, ClientSession] = {}
_stack = AsyncExitStack()

# --- background loop setup -------------------------------------------------
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True, name="mcp-loop")
_loop_thread.start()


def _run_coro(coro):
    """Submit a coroutine to the background loop and block for its result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def _shutdown():
    try:
        _run_coro(_stack.aclose())
    except Exception:
        pass
    _loop.call_soon_threadsafe(_loop.stop)


atexit.register(_shutdown)

# --- session management (runs ON the background loop) ----------------------
async def _get_http_session(key: str, url: str) -> ClientSession:
    if key not in _sessions:
        read, write, _ = await _stack.enter_async_context(streamable_http_client(url))
        session = await _stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        _sessions[key] = session
    return _sessions[key]


async def _get_stdio_session(key: str, command: str, args: list[str], env: dict = None) -> ClientSession:
    if key not in _sessions:
        params = StdioServerParameters(command=command, args=args, env=env)
        read, write = await _stack.enter_async_context(stdio_client(params))
        session = await _stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        _sessions[key] = session
    return _sessions[key]


async def _call(session: ClientSession, tool: str, args: dict) -> str:
    result = await session.call_tool(tool, args)
    return "\n".join(c.text for c in result.content if hasattr(c, "text"))


# --- public sync API (call these from your nodes) ---------------------------
def call_tavily(tool: str, args: dict) -> str:
    async def _run():
        url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={Config.TAVILY_API_KEY}"
        session = await _get_http_session("tavily", url)
        return await _call(session, tool, args)
    return _run_coro(_run())


def call_pdf_report(args: dict) -> str:
    async def _run():
        session = await _get_stdio_session(
            "pdf_report", "npx", ["-y", "markdown2pdf-mcp"],
            env={"M2P_OUTPUT_DIR": str(Config.REPORTS_DIR)},
        )
        return await _call(session, "create_pdf_from_markdown", args)
    return _run_coro(_run())