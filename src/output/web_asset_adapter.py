"""Web output adapter for asset results.

Formats asset operation results for web/JSON display.
Returns dictionaries suitable for FastAPI JSON serialization.
"""

from typing import Dict, Any

from models.result.asset_result import (
    MarketContextResult,
    AssetInfoResult,
    PriceDataResult,
    SentimentEventsResult
)


class WebAssetOutputAdapter:
    """Format and display asset results for web/JSON API."""

    def display_market_context(self, result: MarketContextResult) -> Dict[str, Any]:
        """Display market context as JSON-ready dict.

        Args:
            result: MarketContextResult containing market status information

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "markets": [
                {
                    "code": code,
                    "session": session,
                    "status": status,
                    "trading_day": trading_day,
                    "extended_hours": extended_hours,
                }
                for code, session, status, trading_day, extended_hours in result.markets
            ],
            "count": len(result.markets),
        }

    def display_asset_info(self, result: AssetInfoResult) -> Dict[str, Any]:
        """Display asset info as JSON-ready dict.

        Args:
            result: AssetInfoResult containing asset details

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        output = {
            "asset": {
                "symbol": result.asset.symbol,
                "name": result.asset.name,
                "type": result.asset.asset_type.value if result.asset.asset_type else None,
                "asset_class": result.asset.asset_class.value if result.asset.asset_class else None,
                "currency": result.asset.currency,
                "active": result.asset.is_active,
                "market_code": result.market.code if result.market else None,
            },
            "market": {
                "code": result.market.code,
                "name": result.market.name,
                "timezone": result.market.timezone,
            } if result.market else None,
            "universes": result.universes,
        }

        # Add fundamentals if available
        if result.fundamentals:
            fund = result.fundamentals
            output["fundamentals"] = {
                "market_cap": fund.market_cap,
                "market_cap_display": fund.market_cap_display,
                "shares_outstanding": fund.shares_outstanding,
                "shares_outstanding_display": fund.shares_outstanding_display,
                "sector": fund.sector,
                "industry": fund.industry,
                "sic_code": fund.sic_code,
                "avg_volume_30d": fund.avg_volume_30d,
                "beta": float(fund.beta) if fund.beta else None,
                "pe_ratio": float(fund.pe_ratio) if fund.pe_ratio else None,
                "dividend_yield": float(fund.dividend_yield) if fund.dividend_yield else None,
                "last_updated": fund.last_updated.isoformat(),
            }

        return output

    def display_price_data(self, result: PriceDataResult) -> Dict[str, Any]:
        """Display price data as JSON-ready dict.

        Args:
            result: PriceDataResult containing price information

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        from datetime import datetime

        price = result.asset_price

        # Convert provider_updated_at from int (nanoseconds) to datetime if present
        provider_updated_dt = None
        if price.provider_updated_at:
            # Polygon uses nanoseconds, convert to datetime
            provider_updated_dt = datetime.fromtimestamp(price.provider_updated_at / 1_000_000_000)

        # Convert min_timestamp from int (milliseconds) to datetime if present
        min_timestamp_dt = None
        if price.min_timestamp:
            # Polygon uses milliseconds for minute timestamp
            min_timestamp_dt = datetime.fromtimestamp(price.min_timestamp / 1000)

        return {
            "symbol": price.symbol,
            "is_new_data": result.is_new_data,
            "forced_fetch": result.forced_fetch,
            "provider_updated_at": provider_updated_dt.isoformat() if provider_updated_dt else None,
            "captured_at": price.updated_at.isoformat() if price.updated_at else None,
            "prevday_open": float(price.prevday_open) if price.prevday_open else None,
            "prevday_high": float(price.prevday_high) if price.prevday_high else None,
            "prevday_low": float(price.prevday_low) if price.prevday_low else None,
            "prevday_close": float(price.prevday_close) if price.prevday_close else None,
            "prevday_volume": price.prevday_volume,
            "day_open": float(price.day_open) if price.day_open else None,
            "day_high": float(price.day_high) if price.day_high else None,
            "day_low": float(price.day_low) if price.day_low else None,
            "day_close": float(price.day_close) if price.day_close else None,
            "day_volume": price.day_volume,
            "minute_open": float(price.min_open) if price.min_open else None,
            "minute_high": float(price.min_high) if price.min_high else None,
            "minute_low": float(price.min_low) if price.min_low else None,
            "minute_close": float(price.min_close) if price.min_close else None,
            "minute_volume": price.min_volume,
            "minute_timestamp": min_timestamp_dt.isoformat() if min_timestamp_dt else None,
        }

    def display_sentiment_events(self, result: SentimentEventsResult) -> Dict[str, Any]:
        """Display sentiment events as JSON-ready dict.

        Args:
            result: SentimentEventsResult containing sentiment data

        Returns:
            Dictionary ready for FastAPI JSON serialization
        """
        return {
            "symbol": result.symbol,
            "time_window_days": result.time_window_days,
            "sentiment_events": [
                {
                    "id": event.id,
                    "event_date": event.event_date.isoformat() if event.event_date else None,
                    "event_time": event.event_time.strftime("%H:%M") if event.event_time else None,
                    "sentiment_type_id": event.sentiment_type_id,
                    "sentiment_type": result.type_id_to_name.get(event.sentiment_type_id, "unknown").replace("news_", "").capitalize(),
                    "value": float(event.value) if event.value else None,
                    "magnitude": event.magnitude,
                    "title": event.get_detail("title", "N/A"),
                    "publisher": event.get_detail("publisher", "N/A"),
                    "article_url": event.get_detail("article_url", None),
                    "sentiment_reasoning": event.get_detail("sentiment_reasoning", ""),
                }
                for event in result.sentiment_events
            ],
            "sentiment_score": {
                "score": result.sentiment_score.overall_score,
                "sentiment_label": result.sentiment_score.sentiment_label,
                "confidence_level": result.sentiment_score.confidence_level,
                "positive_count": result.sentiment_score.sentiment_breakdown.get("positive", 0),
                "neutral_count": result.sentiment_score.sentiment_breakdown.get("neutral", 0),
                "negative_count": result.sentiment_score.sentiment_breakdown.get("negative", 0),
                "total_articles": result.sentiment_score.articles_analyzed,
            } if result.sentiment_score else None,
            "count": len(result.sentiment_events),
        }
