from typing import Any
import asyncio
import httpx
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
port = int(os.getenv("PORT", 8085))
mcp = FastMCP("weather", host="0.0.0.0", port=port)

# Constants
WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-app/1.0"

# Get API key from environment variable
API_KEY = os.getenv("WEATHERAPI_KEY")

async def make_weather_request(endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Make a request to the WeatherAPI with proper error handling."""
    # Check if API key is set
    if not API_KEY:
        print("ERROR: WeatherAPI key not set. Please set WEATHERAPI_KEY environment variable.")
        return None
        
    headers = {
        "User-Agent": USER_AGENT,
    }
    # Add API key to parameters
    params["key"] = API_KEY
    
    url = f"{WEATHERAPI_BASE}/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error {e.response.status_code}: {e.response.text}")
            return None
        except httpx.RequestError as e:
            print(f"Request Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None


def _get_mock_current(city: str) -> str:
    """Fallback mock current weather when WeatherAPI key is not configured."""
    normalized = city.strip().lower()
    mock_db = {
        "hanoi": ("Hanoi", "Hanoi", "Vietnam", 29.0, 84.2, 32.0, 89.6, "Trời mưa nhẹ (Light rain)", 82, 12.0, 7.5, "SE", 1008, 4.0, 9.0),
        "haiphong": ("Haiphong", "Haiphong", "Vietnam", 30.0, 86.0, 33.5, 92.3, "Nhiều mây, gió nhẹ (Partly cloudy)", 76, 15.0, 9.3, "E", 1010, 5.0, 10.0),
        "danang": ("Danang", "Danang", "Vietnam", 31.0, 87.8, 35.0, 95.0, "Nắng nhẹ, mây rải rác (Scattered clouds)", 78, 10.0, 6.2, "E", 1009, 6.0, 10.0),
        "ho chi minh": ("Ho Chi Minh City", "Ho Chi Minh", "Vietnam", 33.0, 91.4, 38.0, 100.4, "Mưa rào nhiệt đới (Tropical showers)", 74, 14.0, 8.7, "SW", 1008, 7.0, 8.0),
        "brisbane": ("Brisbane", "Queensland", "Australia", 24.0, 75.2, 24.5, 76.1, "Sunny and pleasant", 55, 18.0, 11.2, "ENE", 1018, 7.0, 10.0),
        "sydney": ("Sydney", "New South Wales", "Australia", 21.5, 70.7, 21.0, 69.8, "Clear skies", 60, 15.0, 9.3, "S", 1020, 5.0, 10.0),
        "tokyo": ("Tokyo", "Tokyo", "Japan", 19.0, 66.2, 19.0, 66.2, "Partly cloudy", 58, 11.0, 6.8, "N", 1016, 4.0, 10.0),
    }

    if normalized in mock_db:
        name, reg, cty, tc, tf, flc, flf, cond, hum, wkph, wmph, wdir, pr, uv, vis = mock_db[normalized]
    else:
        name, reg, cty, tc, tf, flc, flf, cond, hum, wkph, wmph, wdir, pr, uv, vis = (
            city.title(), "Local Region", "Worldwide", 27.0, 80.6, 28.5, 83.3, "Partly cloudy", 70, 12.0, 7.5, "NE", 1012, 5.0, 10.0
        )

    return f"""
Current Weather for {name}, {reg}, {cty}:

Temperature: {tc}°C ({tf}°F)
Feels like: {flc}°C ({flf}°F)
Condition: {cond}
Humidity: {hum}%
Wind: {wkph} km/h ({wmph} mph) {wdir}
Pressure: {pr} mb
UV Index: {uv}
Visibility: {vis} km

[Note: Demo/Mock Data - Set WEATHERAPI_KEY for live data from WeatherAPI.com]
"""


def _get_mock_forecast(city: str, days: int = 3) -> str:
    """Fallback mock forecast weather when WeatherAPI key is not configured."""
    days = min(max(days, 1), 3)
    norm = city.strip().title()
    forecasts = [f"Weather Forecast for {norm}, Region, Country (Next {days} days):"]
    
    import datetime
    today = datetime.date.today()
    
    mock_patterns = [
        {"high": 31, "low": 24, "cond": "Trời nắng nhẹ, chiều có lúc có mưa rào", "rain": 40, "wind": 14, "uv": 6},
        {"high": 30, "low": 23, "cond": "Nhiều mây, thời tiết dịu mát", "rain": 25, "wind": 12, "uv": 5},
        {"high": 32, "low": 25, "cond": "Nắng ráo cả ngày", "rain": 10, "wind": 15, "uv": 7},
    ]
    
    for i in range(days):
        d_date = today + datetime.timedelta(days=i + 1)
        pat = mock_patterns[i % len(mock_patterns)]
        high_f = round(pat["high"] * 9 / 5 + 32, 1)
        low_f = round(pat["low"] * 9 / 5 + 32, 1)
        
        forecasts.append(f"""
{d_date.isoformat()}:
High: {pat['high']}°C ({high_f}°F)
Low: {pat['low']}°C ({low_f}°F)
Condition: {pat['cond']}
Chance of Rain: {pat['rain']}%
Max Wind: {pat['wind']} km/h
UV Index: {pat['uv']}
""")
    forecasts.append("[Note: Demo/Mock Forecast - Set WEATHERAPI_KEY for live data from WeatherAPI.com]")
    return "\n---\n".join(forecasts)


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney")
    """
    params = {
        "q": city,
        "aqi": "no"
    }
    
    data = await make_weather_request("current.json", params)

    if not data:
        return _get_mock_current(city)

    current = data["current"]
    location = data["location"]
    
    return f"""
Current Weather for {location['name']}, {location['region']}, {location['country']}:

Temperature: {current['temp_c']}°C ({current['temp_f']}°F)
Feels like: {current['feelslike_c']}°C ({current['feelslike_f']}°F)
Condition: {current['condition']['text']}
Humidity: {current['humidity']}%
Wind: {current['wind_kph']} km/h ({current['wind_mph']} mph) {current['wind_dir']}
Pressure: {current['pressure_mb']} mb
UV Index: {current['uv']}
Visibility: {current['vis_km']} km

Last updated: {current['last_updated']}
"""

@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Brisbane", "Sydney", "Melbourne")
        days: Number of days to forecast (1-3 for free tier, max 10 for paid)
    """
    # Limit days to 3 for free tier
    days = min(days, 3)
    
    params = {
        "q": city,
        "days": str(days),
        "aqi": "no",
        "alerts": "no"
    }
    
    data = await make_weather_request("forecast.json", params)

    if not data:
        return _get_mock_forecast(city, days)

    location = data["location"]
    forecast_days = data["forecast"]["forecastday"]
    
    forecasts = []
    forecasts.append(f"Weather Forecast for {location['name']}, {location['region']}, {location['country']}:")
    
    for day in forecast_days:
        day_data = day["day"]
        date = day["date"]
        
        forecast = f"""
{date}:
High: {day_data['maxtemp_c']}°C ({day_data['maxtemp_f']}°F)
Low: {day_data['mintemp_c']}°C ({day_data['mintemp_f']}°F)
Condition: {day_data['condition']['text']}
Chance of Rain: {day_data['daily_chance_of_rain']}%
Max Wind: {day_data['maxwind_kph']} km/h
UV Index: {day_data['uv']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def health_check() -> str:
    """Health check endpoint for deployment verification."""
    return "✅ Weather MCP Server is running! Ready to provide weather data for Australian cities and worldwide."

print("✅ MCP server initialized with Streamable HTTP transport")
print("🔧 Available tools: get_current_weather, get_forecast, health_check")

if __name__ == "__main__":
    # Determine transport: command line flags take precedence, then env var, default to streamable-http
    transport = os.getenv("MCP_TRANSPORT", "").strip().lower()
    if "--stdio" in sys.argv:
        transport = "stdio"
    elif "--streamable-http" in sys.argv or "--http" in sys.argv:
        transport = "streamable-http"

    if not transport:
        # Default to streamable-http so running directly or as a background service
        # always starts the HTTP server on port 8085 as expected by the ADK client
        transport = "streamable-http"

    if transport == "streamable-http":
        print(f"🚀 Starting MCP server on http://0.0.0.0:{port}/mcp")
        mcp.run(transport="streamable-http")
    else:
        print("Starting FastMCP server in stdio mode for local client", file=sys.stderr)
        mcp.run()