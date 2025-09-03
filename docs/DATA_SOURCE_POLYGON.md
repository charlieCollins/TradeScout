# Polygon.io Data Source

## Overview
Polygon.io provides real-time and historical market data including stocks, options, forex, and crypto. This is our primary data source for after-hours and premarket trading data.

## Account Details
- **Account Type**: Paid subscription
- **API Key**: `HcbSpRgH0pXVMMY7A6nv_prpkeR0wG19`
- **Documentation**: https://polygon.io/docs

## Key Features
- Real-time market data
- After-hours and premarket trading data
- Historical data
- Options data
- Forex and crypto data
- News and financial data

## Extended Hours Data Support
Polygon provides tick-level market data during extended trading hours:
- **Pre-market**: 4:00 AM EST - 9:30 AM EST
- **Regular hours**: 9:30 AM EST - 4:00 PM EST  
- **After-hours**: 4:00 PM EST - 8:00 PM EST

**Important Note**: Most extended hour trades have "Sale Conditions" that prevent them from updating aggregates, so there may be fewer aggregates during pre-market and after-hours compared to regular trading hours. Users can filter for specific time periods using UTC timestamps in the 'from' and 'to' parameters of the Aggregates endpoint.

## Rate Limits
- Varies by subscription tier
- Check current plan limits in Polygon.io dashboard

## Usage in TradeScout
- Primary source for extended hours trading data
- Real-time price quotes
- Historical data for backtesting
- Market data aggregation

## Configuration
The API key is configured in the data sources configuration system. Ensure the key is properly set in your environment or configuration files.

## Notes
- Purchased to replace Tiingo for after-hours/premarket data
- Tiingo's IEX path doesn't provide the real-time extended hours data we need
- Polygon.io should provide the real-time extended hours coverage required