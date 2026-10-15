#!/usr/bin/env python3
"""Unified End-to-End Test Suite for Day 26 MCP & Function Calling Lab.

Tự động kiểm thử toàn diện cả 4 module:
  - Module 01: Function Calling thuần (Schema + Execution Loop + Fallback Simulation)
  - Module 02: MCP Basics (stdio transport + list_tools + call_tool)
  - Module 03: Production Patterns:
      * 3A: Auth (Streamable HTTP, valid/invalid/missing tokens)
      * 3B: Tool Registry & Discovery (Search by tag, keyword, semantic best_match)
      * 3C: Versioning & Backward Compatibility (Resource server://info, tool v1 & v2)
  - Module 04: Lab Weather Server & ADK McpToolset (FastMCP HTTP + Tools + ADK Agent)

Cách chạy:
    .venv/Scripts/python verify_all.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).parent.resolve()

# Load biến môi trường từ .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

import httpx
from packaging.version import Version
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

# Kết quả kiểm thử
TEST_RESULTS: list[tuple[str, bool, str]] = []


def record_result(name: str, passed: bool, detail: str = "") -> None:
    TEST_RESULTS.append((name, passed, detail))
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{status}] {name} {f'({detail})' if detail else ''}")


# =====================================================================
# 1. Test Module 01: Function Calling Thuần
# =====================================================================
def test_module_01() -> None:
    print("\n" + "=" * 70)
    print("▶ KIỂM THỬ MODULE 01: Function Calling thuần")
    print("=" * 70)
    try:
        sys.path.insert(0, str(ROOT_DIR / "01-function-calling"))
        import weather_function_calling as fc

        # Kiểm tra schema declaration
        assert fc.get_weather_declaration.name == "get_weather"
        assert len(fc.TOOLS) == 1
        record_result("01.1 Khai báo schema FunctionDeclaration thủ công", True)

        # Kiểm tra hàm get_weather thực thi tại app
        res_hanoi = fc.get_weather("Hà Nội")
        data = json.loads(res_hanoi)
        assert data["city"] == "Hà Nội"
        assert "nhiệt_độ" in data
        record_result("01.2 App tự thực thi hàm get_weather()", True, f"Nhiệt độ: {data['nhiệt_độ']}")

        # Kiểm tra vòng lặp Function Calling (live hoặc simulation)
        output = fc.run("Thời tiết Hà Nội và Đà Nẵng hôm nay?")
        assert len(output) > 20
        mode = "Live Gemini" if fc.api_key else "Simulation Mode"
        record_result("01.3 Chu trình Function Calling Model <-> App", True, f"Chế độ: {mode}")

    except Exception as e:
        record_result("01. Function Calling", False, str(e))
    finally:
        if str(ROOT_DIR / "01-function-calling") in sys.path:
            sys.path.remove(str(ROOT_DIR / "01-function-calling"))


# =====================================================================
# 2. Test Module 02: MCP Basics (stdio transport)
# =====================================================================
async def test_module_02() -> None:
    print("\n" + "=" * 70)
    print("▶ KIỂM THỬ MODULE 02: MCP Basics (stdio transport)")
    print("=" * 70)
    server_script = str(ROOT_DIR / "02-mcp-basics" / "weather_server.py")
    params = StdioServerParameters(command=sys.executable, args=[server_script])

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. Khám phá tool
                tools_res = await session.list_tools()
                tool_names = [t.name for t in tools_res.tools]
                assert "get_weather" in tool_names
                record_result("02.1 Khám phá công cụ qua session.list_tools()", True, f"Tools: {tool_names}")

                # 2. Gọi tool qua MCP
                call_res = await session.call_tool("get_weather", {"city": "Hanoi"})
                text = call_res.content[0].text
                assert "Hanoi: 29°C" in text
                record_result("02.2 Thực thi tool get_weather qua MCP stdio", True, text.strip())

    except Exception as e:
        record_result("02. MCP Basics stdio", False, str(e))


# =====================================================================
# 3. Test Module 03: Production Patterns
# =====================================================================
async def test_module_03() -> None:
    print("\n" + "=" * 70)
    print("▶ KIỂM THỬ MODULE 03: Production (Auth, Registry, Versioning)")
    print("=" * 70)

    # ---------------- 3A: Authentication ----------------
    auth_server_script = str(ROOT_DIR / "03-production" / "auth_server.py")
    server_proc = subprocess.Popen(
        [sys.executable, auth_server_script],
        cwd=str(ROOT_DIR / "03-production"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    time.sleep(2.5)  # Chờ server khởi động

    try:
        auth_url = "http://localhost:8000/mcp"
        valid_token = "dev-token-abc123"

        # 3A.1 Token hợp lệ
        http_client = create_mcp_http_client(headers={"Authorization": f"Bearer {valid_token}"})
        async with http_client:
            async with streamable_http_client(auth_url, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert len(tools.tools) >= 1
                    call_res = await session.call_tool("get_weather", {"city": "Hanoi"})
                    assert "Hanoi" in call_res.content[0].text
                    record_result("03.1 Auth - Token hợp lệ (200 OK)", True, call_res.content[0].text.strip())

        # 3A.2 Token không hợp lệ
        rejected_invalid = False
        try:
            bad_client = create_mcp_http_client(headers={"Authorization": "Bearer bad-token-999"})
            async with bad_client:
                async with streamable_http_client(auth_url, http_client=bad_client) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except Exception:
            rejected_invalid = True
        assert rejected_invalid, "Server phải từ chối token không hợp lệ"
        record_result("03.2 Auth - Từ chối token sai (401/403)", True)

        # 3A.3 Không gửi token
        rejected_missing = False
        try:
            no_token_client = create_mcp_http_client(headers={})
            async with no_token_client:
                async with streamable_http_client(auth_url, http_client=no_token_client) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except Exception:
            rejected_missing = True
        assert rejected_missing, "Server phải từ chối request thiếu token"
        record_result("03.3 Auth - Từ chối request thiếu Authorization", True)

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    # ---------------- 3B: Tool Registry & Discovery ----------------
    sys.path.insert(0, str(ROOT_DIR / "03-production"))
    try:
        import registry_client as reg_mod

        registry = reg_mod.ToolRegistry()
        weather_tools = registry.search(tag="weather")
        assert len(weather_tools) >= 2
        record_result("03.4 Tool Registry - Tìm kiếm theo tag 'weather'", True, f"Tìm thấy {len(weather_tools)} tools")

        best = registry.best_match(tag="weather")
        assert best["tool"] == "get_weather_v2"
        assert best["version"] == "2.0.0"
        record_result("03.5 Tool Registry - Chọn best match theo SemVer", True, f"Best match: {best['tool']} v{best['version']}")

        forecast_tools = registry.search(keyword="forecast")
        assert len(forecast_tools) >= 1
        record_result("03.6 Tool Registry - Tìm kiếm theo keyword 'forecast'", True, f"{forecast_tools[0]['tool']}")

        call_output = await reg_mod.connect_and_call(best, {"city": "Hanoi"})
        assert "api_version" in call_output
        record_result("03.7 Tool Registry - Động kết nối server và gọi tool", True, "Gọi v2 thành công")

    finally:
        if str(ROOT_DIR / "03-production") in sys.path:
            sys.path.remove(str(ROOT_DIR / "03-production"))

    # ---------------- 3C: Versioning & Backward Compatibility ----------------
    ver_server_script = str(ROOT_DIR / "03-production" / "versioned_server.py")
    params = StdioServerParameters(command=sys.executable, args=[ver_server_script])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Đọc resource server://info
            info = await session.read_resource("server://info")
            meta = json.loads(info.contents[0].text)
            assert meta["version"] == "2.0.0"
            assert "get_weather" in meta["deprecated_tools"]
            record_result("03.8 Versioning - Đọc metadata resource server://info", True, f"Version: {meta['version']}")

            # Gọi v1 deprecated
            r1 = await session.call_tool("get_weather", {"city": "Hanoi"})
            assert "29°C" in r1.content[0].text
            record_result("03.9 Versioning - Gọi tool v1 (Deprecated vẫn hoạt động)", True, r1.content[0].text.strip())

            # Gọi v2 nâng cao
            r2 = await session.call_tool("get_weather_v2", {"city": "Hanoi", "include_forecast": True})
            v2_data = json.loads(r2.content[0].text)
            assert v2_data["api_version"] == "2.0"
            assert "forecast" in v2_data
            record_result("03.10 Versioning - Gọi tool v2 (Có dự báo 2 ngày)", True, f"Forecast days: {len(v2_data['forecast'])}")


# =====================================================================
# 4. Test Module 04: Lab Weather Server & Google ADK Toolset
# =====================================================================
async def test_module_04() -> None:
    print("\n" + "=" * 70)
    print("▶ KIỂM THỬ MODULE 04: Lab Weather Server & Google ADK")
    print("=" * 70)

    server_script = str(ROOT_DIR / "04-lab" / "mcp-server" / "weather.py")
    env = os.environ.copy()
    env["PORT"] = "8085"
    env["MCP_TRANSPORT"] = "streamable-http"
    env["PYTHONUTF8"] = "1"

    server_proc = subprocess.Popen(
        ["uv", "run", "python", "weather.py"],
        cwd=str(ROOT_DIR / "04-lab" / "mcp-server"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    time.sleep(3.0)  # Chờ server khởi động

    try:
        server_url = "http://localhost:8085/mcp"

        # 4.1 Kiểm tra HTTP Server endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.get(server_url, timeout=10.0)
            assert resp.status_code < 500
            record_result("04.1 FastMCP Server lắng nghe cổng 8085", True, f"HTTP {resp.status_code}")

        # 4.2 Kiểm tra các tool qua MCP Client Session
        http_client = create_mcp_http_client()
        async with http_client:
            async with streamable_http_client(server_url, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = [t.name for t in tools.tools]
                    assert "get_current_weather" in names
                    assert "get_forecast" in names
                    assert "health_check" in names
                    record_result("04.2 Khám phá 3 Tools từ FastMCP Server", True, f"Tools: {names}")

                    # Test health_check
                    hc = await session.call_tool("health_check", {})
                    assert "✅" in hc.content[0].text or "running" in hc.content[0].text.lower()
                    record_result("04.3 Thực thi tool health_check()", True)

                    # Test get_current_weather
                    cw = await session.call_tool("get_current_weather", {"city": "Hanoi"})
                    assert "Hanoi" in cw.content[0].text
                    record_result("04.4 Thực thi tool get_current_weather('Hanoi')", True)

                    # Test get_forecast
                    fc = await session.call_tool("get_forecast", {"city": "Brisbane", "days": 2})
                    assert "Brisbane" in fc.content[0].text
                    record_result("04.5 Thực thi tool get_forecast('Brisbane', days=2)", True)

        # 4.3 Kiểm tra nạp ADK Agent trong mcp-client
        adk_check = subprocess.run(
            ["uv", "run", "python", "-c", "import warnings; warnings.filterwarnings('ignore'); from weather_agent import root_agent; print(root_agent.name)"],
            cwd=str(ROOT_DIR / "04-lab" / "mcp-client"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        assert adk_check.returncode == 0
        assert "weather_agent" in adk_check.stdout
        record_result("04.6 Google ADK McpToolset & Root Agent Initialization", True, "weather_agent ready")

    except Exception as e:
        record_result("04. Lab 04 Weather Agent", False, str(e))
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()


# =====================================================================
# Main runner
# =====================================================================
async def main_async() -> int:
    print("=" * 70)
    print("       BỘ KIỂM THỬ TỰ ĐỘNG TOÀN DIỆN (DAY 26 LAB TEST SUITE)")
    print("=" * 70)

    test_module_01()
    await test_module_02()
    await test_module_03()
    await test_module_04()

    print("\n" + "=" * 70)
    print("                 BẢNG TỔNG KẾT KẾT QUẢ KIỂM THỬ")
    print("=" * 70)

    total = len(TEST_RESULTS)
    passed = sum(1 for _, ok, _ in TEST_RESULTS if ok)
    failed = total - passed

    for name, ok, detail in TEST_RESULTS:
        icon = "✅ PASS" if ok else "❌ FAIL"
        det = f" -- {detail}" if detail else ""
        print(f" {icon:8} | {name}{det}")

    print("-" * 70)
    print(f" Tổng cộng: {total} bài test | Thành công: {passed} | Thất bại: {failed}")
    if failed == 0:
        print(" 🎉 TOÀN BỘ CÁC MODULE 01, 02, 03, 04 ĐẠT 100% TIÊU CHUẨN!")
        return 0
    else:
        print(f" ⚠️ Có {failed} bài test chưa vượt qua. Vui lòng kiểm tra lại log.")
        return 1


if __name__ == "__main__":
    code = asyncio.run(main_async())
    sys.exit(code)
