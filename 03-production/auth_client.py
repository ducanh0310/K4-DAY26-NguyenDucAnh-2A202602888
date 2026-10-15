"""MCP Client có Authentication — kết nối tới auth_server.py qua HTTP.

Client tạo HTTP client bằng create_mcp_http_client(headers=...) của MCP SDK
(đúng thư viện HTTP mà SDK dùng bên dưới, kèm timeout khuyến nghị). Header
Authorization được gắn vào mọi request HTTP (POST, GET, DELETE) tới server.

Cách chạy (cần auth_server.py đang chạy ở terminal khác):
    cd 03-production
    python auth_server.py            # terminal 1
    python auth_client.py            # terminal 2
"""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

SERVER_URL = "http://localhost:8000/mcp"
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "dev-token-abc123")


async def test_auth_scenario(token: str | None, scenario_name: str) -> bool:
    """Kiểm tra một kịch bản xác thực (hợp lệ hoặc không hợp lệ)."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    print(f"\n=== [Kịch bản] {scenario_name} ===")
    if token:
        print(f"  Gửi token: {token}")
    else:
        print("  Không gửi header Authorization")

    try:
        http_client = create_mcp_http_client(headers=headers)
        async with http_client:
            async with streamable_http_client(SERVER_URL, http_client=http_client) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    print(f"  ✅ Thành công: Server xác thực hợp lệ! Số tools: {len(tools.tools)}")
                    for t in tools.tools:
                        print(f"     - {t.name}: {t.description}")

                    result = await session.call_tool("get_weather", {"city": "Hanoi"})
                    print(f"  ✅ Gọi tool get_weather('Hanoi') thành công:")
                    print(f"     -> {result.content[0].text}")
                    return True
    except Exception as e:
        print(f"  🔒 Server từ chối truy cập (Bảo mật hoạt động đúng):")
        print(f"     -> {type(e).__name__}: {e}")
        return False


async def main() -> None:
    print("=" * 60)
    print("MCP Authentication & Security Test Suite")
    print(f"Mục tiêu server: {SERVER_URL}")
    print("=" * 60)

    # 1. Kịch bản 1: Token hợp lệ
    await test_auth_scenario(TOKEN, "1. Gửi Token HỢP LỆ (dev-token)")

    # 2. Kịch bản 2: Token sai
    await test_auth_scenario("invalid-token-xyz999", "2. Gửi Token KHÔNG HỢP LỆ")

    # 3. Kịch bản 3: Không có Token
    await test_auth_scenario(None, "3. KHÔNG GỬI Token (Missing Header)")

    print("\n" + "=" * 60)
    print("Hoàn tất kiểm thử các kịch bản Auth!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
