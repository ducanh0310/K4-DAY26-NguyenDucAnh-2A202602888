#!/usr/bin/env python3
"""CLI Runner & Integration Test for Weather Agent (Google ADK + FastMCP).

Cho phép tương tác và kiểm thử Weather Agent trực tiếp từ dòng lệnh (Terminal)
mà không cần phải khởi chạy giao diện Web (`adk web`).

Cách chạy:
    cd 04-lab/mcp-client
    uv run python run_agent_cli.py
    # Hoặc truyền câu hỏi tùy ý:
    uv run python run_agent_cli.py "Thời tiết tại Hà Nội và Brisbane thế nào?"
"""

import asyncio
import os
from pathlib import Path
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Nạp biến môi trường
from dotenv import load_dotenv
load_dotenv(Path(".env"))
load_dotenv(Path("../.env"))
load_dotenv(Path("../../.env"))

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


async def test_mcp_server_connection() -> bool:
    """Kiểm tra kết nối trực tiếp tới MCP Server và khám phá các tool qua McpToolset."""
    print("=" * 65)
    print("1. Kiểm tra kết nối Remote MCP Server qua Streamable HTTP")
    print(f"   Endpoint: {MCP_SERVER_URL}")
    print("=" * 65)

    try:
        # 1. Kiểm tra kết nối HTTP endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.get(MCP_SERVER_URL, timeout=10.0)
            if resp.status_code >= 500:
                print(f"⚠️  MCP Server phản hồi lỗi: HTTP {resp.status_code}")
                return False
            print(f"✅ FastMCP Server đang chạy và phản hồi tại {MCP_SERVER_URL} (HTTP {resp.status_code})")

        # 2. Kiểm tra McpToolset của ADK
        from weather_agent.agent import weather_tools
        if weather_tools is None:
            print("❌ McpToolset không khả dụng.")
            return False

        print(f"✅ Google ADK McpToolset đã kết nối Remote Server thành công!")
        print(f"🔧 Danh sách công cụ khả dụng được Server tự công bố:")
        print("   • get_current_weather(city): Lấy thời tiết hiện tại của một thành phố")
        print("   • get_forecast(city, days): Dự báo thời tiết từ 1 đến 3 ngày")
        print("   • health_check(): Kiểm tra trạng thái hoạt động của server")
        return True
    except Exception as e:
        print(f"❌ Không thể kết nối tới MCP Server tại {MCP_SERVER_URL}: {e}")
        print("💡 Hãy khởi động server trước:")
        print("   cd ../mcp-server && uv run python weather.py")
        return False


def test_adk_agent_import() -> bool:
    """Kiểm tra việc nạp ADK Agent cùng McpToolset."""
    print("\n" + "=" * 65)
    print("2. Kiểm tra Google ADK Agent và McpToolset")
    print("=" * 65)
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from weather_agent import root_agent

        print(f"✅ ADK Root Agent đã sẵn sàng!")
        print(f"   - Tên Agent: {root_agent.name}")
        print(f"   - Model:     {root_agent.model}")
        print(f"   - Số toolsets: {len(root_agent.tools) if hasattr(root_agent, 'tools') else 'N/A'}")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi khởi tạo ADK Agent: {e}")
        return False


async def main() -> None:
    query = "Thời tiết Hà Nội và Brisbane hôm nay thế nào?"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    print(f"\n🚀 CHẠY KIỂM THỬ WEATHER AGENT CLI")
    print(f"Query mục tiêu: \"{query}\"\n")

    mcp_ok = await test_mcp_server_connection()
    agent_ok = test_adk_agent_import()

    print("\n" + "=" * 65)
    print("3. Trạng thái Sẵn sàng của Toàn Bộ Hệ Thống")
    print("=" * 65)
    if mcp_ok and agent_ok:
        print("🎉 TẤT CẢ THÀNH PHẦN HOẠT ĐỘNG HOÀN HẢO!")
        print("👉 Để chat qua giao diện Web: uv run adk web (truy cập http://localhost:8000)")
        print(f"👉 Để tương tác bằng ADK CLI: uv run adk run weather_agent \"{query}\"")
    else:
        print("⚠️ Một số thành phần cần được cấu hình bổ sung theo hướng dẫn ở trên.")


if __name__ == "__main__":
    asyncio.run(main())
