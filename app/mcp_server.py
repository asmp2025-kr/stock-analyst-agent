import sys
from mcp.server.fastmcp import FastMCP

# Create the FastMCP server instance
mcp = FastMCP("Stock Analyst MCP Server")

# Simulated database of stock tickers
STOCK_DATABASE = {
    "AAPL": {
        "price": 185.50,
        "change": "+1.25%",
        "volume": "52M",
        "pe_ratio": 28.5,
        "market_cap": "2.9T",
        "debt_equity": 1.45,
        "revenue_growth": "+8.5%",
        "sentiment": "Highly Bullish. Strong demand for AI integrations in ecosystem.",
    },
    "GOOG": {
        "price": 172.80,
        "change": "+2.10%",
        "volume": "28M",
        "pe_ratio": 24.2,
        "market_cap": "2.15T",
        "debt_equity": 0.35,
        "revenue_growth": "+14.2%",
        "sentiment": "Bullish. Dominance in search ads and rapid growth in Google Cloud AI.",
    },
    "MSFT": {
        "price": 420.15,
        "change": "-0.45%",
        "volume": "22M",
        "pe_ratio": 35.1,
        "market_cap": "3.12T",
        "debt_equity": 0.85,
        "revenue_growth": "+12.8%",
        "sentiment": "Neutral. High valuation but sustained strong enterprise cloud performance.",
    },
    "TSLA": {
        "price": 182.20,
        "change": "-4.80%",
        "volume": "88M",
        "pe_ratio": 58.2,
        "market_cap": "580B",
        "debt_equity": 0.12,
        "revenue_growth": "+2.1%",
        "sentiment": "Bearish. Margin pressure due to EV pricing wars and macro slowdown.",
    },
}

DEFAULT_STOCK = {
    "price": 100.00,
    "change": "+0.00%",
    "volume": "10M",
    "pe_ratio": 15.0,
    "market_cap": "10B",
    "debt_equity": 0.50,
    "revenue_growth": "+5.0%",
    "sentiment": "Neutral. Limited news and baseline market trading patterns.",
}


@mcp.tool()
def get_stock_price(ticker: str) -> str:
    """Fetch technical stock price, daily change, and trading volume.

    Args:
        ticker: The stock ticker symbol (e.g. AAPL, GOOG, TSLA).
    """
    symbol = ticker.strip().upper()
    data = STOCK_DATABASE.get(symbol, DEFAULT_STOCK)
    return (
        f"Technical Metrics for {symbol}:\n"
        f"- Current Price: ${data['price']:.2f}\n"
        f"- Daily Change: {data['change']}\n"
        f"- Volume: {data['volume']}"
    )


@mcp.tool()
def get_company_fundamentals(ticker: str) -> str:
    """Fetch fundamental metrics (P/E ratio, Market Cap, Debt-to-Equity, Revenue Growth).

    Args:
        ticker: The stock ticker symbol (e.g. AAPL, GOOG, TSLA).
    """
    symbol = ticker.strip().upper()
    data = STOCK_DATABASE.get(symbol, DEFAULT_STOCK)
    return (
        f"Fundamental Metrics for {symbol}:\n"
        f"- Market Cap: {data['market_cap']}\n"
        f"- P/E Ratio: {data['pe_ratio']}\n"
        f"- Debt-to-Equity: {data['debt_equity']}\n"
        f"- Revenue Growth: {data['revenue_growth']}"
    )


@mcp.tool()
def get_market_sentiment(ticker: str) -> str:
    """Fetch current market sentiment and news insights.

    Args:
        ticker: The stock ticker symbol (e.g. AAPL, GOOG, TSLA).
    """
    symbol = ticker.strip().upper()
    data = STOCK_DATABASE.get(symbol, DEFAULT_STOCK)
    return f"Market Sentiment for {symbol}:\n- Insight: {data['sentiment']}"


if __name__ == "__main__":
    mcp.run()
