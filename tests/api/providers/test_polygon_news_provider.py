"""Unit tests for PolygonNewsProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from datetime import date

from api.providers.polygon_news_provider import PolygonNewsProvider


class TestPolygonNewsProvider:
    """Test PolygonNewsProvider API operations."""

    @pytest.fixture
    def provider(self):
        """Create PolygonNewsProvider instance with test API key."""
        return PolygonNewsProvider(api_key="test_api_key_12345")

    @pytest.fixture
    def sample_news_response(self):
        """Sample Polygon API response for news articles."""
        return {
            "status": "OK",
            "results": [
                {
                    "id": "article1",
                    "publisher": {"name": "MarketWatch"},
                    "title": "Apple announces record earnings",
                    "author": "John Doe",
                    "published_utc": "2024-01-15T14:30:00Z",
                    "article_url": "https://example.com/article1",
                    "tickers": ["AAPL"],
                    "description": "Apple Inc. reported record earnings...",
                    "keywords": ["earnings", "revenue", "iPhone"],
                    "insights": [
                        {
                            "ticker": "AAPL",
                            "sentiment": "positive",
                            "reasoning": "Strong earnings beat expectations",
                            "sentiment_score": 0.75
                        }
                    ]
                },
                {
                    "id": "article2",
                    "publisher": {"name": "Bloomberg"},
                    "title": "Apple faces regulatory challenges",
                    "author": "Jane Smith",
                    "published_utc": "2024-01-15T10:00:00Z",
                    "article_url": "https://example.com/article2",
                    "tickers": ["AAPL"],
                    "description": "Apple is facing new regulatory challenges...",
                    "keywords": ["regulation", "antitrust"],
                    "insights": [
                        {
                            "ticker": "AAPL",
                            "sentiment": "negative",
                            "reasoning": "Regulatory uncertainty",
                            "sentiment_score": -0.5
                        }
                    ]
                }
            ]
        }

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_provider_initialization(self):
        """Test provider initializes with API key."""
        provider = PolygonNewsProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.polygon.io"

    def test_provider_initialization_no_api_key(self):
        """Test provider raises error without API key."""
        with pytest.raises(ValueError, match="requires an API key"):
            PolygonNewsProvider(api_key="")

    def test_provider_info(self, provider):
        """Test provider info returns correct metadata."""
        info = provider.get_provider_info()
        assert info["name"] == "polygon_news"
        assert info["base_url"] == "https://api.polygon.io"
        assert "news" in info["endpoints"]

    def test_add_authentication(self, provider):
        """Test authentication adds API key to params."""
        params = {}
        authed_params = provider._add_authentication(params)
        assert "apikey" in authed_params
        assert authed_params["apikey"] == "test_api_key_12345"

    # ============================================================================
    # FETCH NEWS TESTS
    # ============================================================================

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_success(self, mock_request, provider, sample_news_response):
        """Test fetching news for ticker successfully."""
        mock_request.return_value = sample_news_response

        result = provider.fetch_news_for_ticker("AAPL")

        assert result is not None
        assert len(result) == 2
        assert all(isinstance(article, dict) for article in result)
        assert result[0]["title"] == "Apple announces record earnings"
        assert result[1]["title"] == "Apple faces regulatory challenges"

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_with_limit(self, mock_request, provider, sample_news_response):
        """Test fetching news with custom limit."""
        mock_request.return_value = sample_news_response

        result = provider.fetch_news_for_ticker("AAPL", limit=5)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        params = call_args[0][1]
        assert params["ticker"] == "AAPL"
        assert params["limit"] == 5

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_with_date_filter(self, mock_request, provider, sample_news_response):
        """Test fetching news with date filter."""
        mock_request.return_value = sample_news_response
        filter_date = date(2024, 1, 1)

        result = provider.fetch_news_for_ticker("AAPL", published_after=filter_date)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        params = call_args[0][1]
        assert params["published_utc.gte"] == "2024-01-01"

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_empty_response(self, mock_request, provider):
        """Test fetching news with empty results."""
        mock_request.return_value = {"status": "OK", "results": []}

        result = provider.fetch_news_for_ticker("AAPL")

        assert result is not None
        assert len(result) == 0

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_no_results_key(self, mock_request, provider):
        """Test fetching news when response has no results key."""
        mock_request.return_value = {"status": "OK"}

        result = provider.fetch_news_for_ticker("AAPL")

        assert result is not None
        assert len(result) == 0

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_fetch_news_for_ticker_api_error(self, mock_request, provider):
        """Test fetching news handles API errors."""
        mock_request.side_effect = Exception("API Error")

        result = provider.fetch_news_for_ticker("AAPL")

        assert result is None

    # ============================================================================
    # SENTIMENT EXTRACTION TESTS
    # ============================================================================

    def test_extract_sentiment_from_article_with_insights(self, provider):
        """Test extracting sentiment from article with insights."""
        article = {
            "id": "article1",
            "title": "Test Article",
            "published_utc": "2024-01-15T14:30:00Z",
            "insights": [
                {
                    "ticker": "AAPL",
                    "sentiment": "positive",
                    "sentiment_reasoning": "Good news",
                    "sentiment_score": 0.8
                },
                {
                    "ticker": "MSFT",
                    "sentiment": "neutral",
                    "sentiment_reasoning": "Mixed signals",
                    "sentiment_score": 0.0
                }
            ]
        }

        result = provider.extract_sentiment_from_article(article, "AAPL")

        assert result is not None
        assert result["sentiment"] == "positive"
        assert result["sentiment_score"] == 0.8
        assert result["reasoning"] == "Good news"

    def test_extract_sentiment_from_article_no_insights(self, provider):
        """Test extracting sentiment when article has no insights."""
        article = {
            "id": "article1",
            "title": "Test Article",
            "published_utc": "2024-01-15T14:30:00Z"
        }

        result = provider.extract_sentiment_from_article(article, "AAPL")

        assert result is None

    def test_extract_sentiment_from_article_ticker_not_found(self, provider):
        """Test extracting sentiment when ticker not in insights."""
        article = {
            "id": "article1",
            "title": "Test Article",
            "insights": [
                {
                    "ticker": "MSFT",
                    "sentiment": "positive",
                    "sentiment_score": 0.5
                }
            ]
        }

        result = provider.extract_sentiment_from_article(article, "AAPL")

        assert result is None

    def test_extract_sentiment_from_article_multiple_tickers(self, provider):
        """Test extracting sentiment finds correct ticker in multi-ticker article."""
        article = {
            "id": "article1",
            "title": "Tech stocks rally",
            "insights": [
                {
                    "ticker": "AAPL",
                    "sentiment": "positive",
                    "sentiment_score": 0.7
                },
                {
                    "ticker": "MSFT",
                    "sentiment": "positive",
                    "sentiment_score": 0.6
                },
                {
                    "ticker": "GOOGL",
                    "sentiment": "neutral",
                    "sentiment_score": 0.1
                }
            ]
        }

        result = provider.extract_sentiment_from_article(article, "MSFT")

        assert result is not None
        assert result["sentiment"] == "positive"
        assert result["sentiment_score"] == 0.6

    def test_extract_sentiment_handles_missing_fields(self, provider):
        """Test sentiment extraction handles missing optional fields."""
        article = {
            "id": "article1",
            "insights": [
                {
                    "ticker": "AAPL",
                    "sentiment": "positive"
                    # Missing sentiment_score and reasoning
                }
            ]
        }

        result = provider.extract_sentiment_from_article(article, "AAPL")

        # Should return None or handle gracefully
        assert result is None or (result["sentiment"] == "positive" and "sentiment_score" in result)

    # ============================================================================
    # HEALTH CHECK TESTS
    # ============================================================================

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_health_check_success(self, mock_request, provider):
        """Test health check succeeds."""
        mock_request.return_value = {"status": "OK"}

        result = provider.health_check()

        assert result is True
        mock_request.assert_called_once_with("/v1/marketstatus/now")

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_health_check_failure(self, mock_request, provider):
        """Test health check fails on API error."""
        mock_request.side_effect = Exception("API Error")

        result = provider.health_check()

        assert result is False
