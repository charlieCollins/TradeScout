"""Unit tests for PolygonNewsProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from datetime import date, datetime

import sys
sys.path.insert(0, '/home/ccollins/projects/TradeScout/src')

from api.providers.polygon_news_provider import PolygonNewsProvider
from models.dataclass.news_article import NewsArticle, SentimentInsight


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
        assert all(isinstance(article, NewsArticle) for article in result)
        assert result[0].title == "Apple announces record earnings"
        assert result[1].title == "Apple faces regulatory challenges"
        assert result[0].publisher_name == "MarketWatch"
        assert result[1].publisher_name == "Bloomberg"

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
    # NEWSARTICLE DATACLASS TESTS
    # ============================================================================

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_newsarticle_attributes(self, mock_request, provider, sample_news_response):
        """Test NewsArticle dataclass has correct attributes."""
        mock_request.return_value = sample_news_response

        articles = provider.fetch_news_for_ticker("AAPL")

        article = articles[0]
        assert article.id == "article1"
        assert article.title == "Apple announces record earnings"
        assert article.article_url == "https://example.com/article1"
        assert article.publisher_name == "MarketWatch"
        assert article.author == "John Doe"
        assert article.description == "Apple Inc. reported record earnings..."
        assert "AAPL" in article.tickers
        assert "earnings" in article.keywords
        assert isinstance(article.published_utc, datetime)

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_sentiment_insights_transformation(self, mock_request, provider, sample_news_response):
        """Test sentiment insights are properly transformed to dataclass."""
        mock_request.return_value = sample_news_response

        articles = provider.fetch_news_for_ticker("AAPL")

        article = articles[0]
        assert len(article.insights) == 1

        insight = article.insights[0]
        assert isinstance(insight, SentimentInsight)
        assert insight.ticker == "AAPL"
        assert insight.sentiment == "positive"
        assert insight.sentiment_score == 0.75
        assert insight.sentiment_reasoning == "Strong earnings beat expectations"

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_get_insight_for_ticker_method(self, mock_request, provider, sample_news_response):
        """Test NewsArticle.get_insight_for_ticker() helper method."""
        mock_request.return_value = sample_news_response

        articles = provider.fetch_news_for_ticker("AAPL")

        article = articles[0]
        insight = article.get_insight_for_ticker("AAPL")

        assert insight is not None
        assert insight.sentiment == "positive"
        assert insight.sentiment_score == 0.75

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_get_insight_for_ticker_not_found(self, mock_request, provider, sample_news_response):
        """Test get_insight_for_ticker returns None for missing ticker."""
        mock_request.return_value = sample_news_response

        articles = provider.fetch_news_for_ticker("AAPL")

        article = articles[0]
        insight = article.get_insight_for_ticker("MSFT")  # Not in this article

        assert insight is None

    @patch.object(PolygonNewsProvider, "_make_request")
    def test_multiple_insights_per_article(self, mock_request, provider):
        """Test article with multiple ticker insights."""
        multi_ticker_response = {
            "status": "OK",
            "results": [
                {
                    "id": "multi1",
                    "publisher": {"name": "Reuters"},
                    "title": "Tech giants rally",
                    "author": "Test Author",
                    "published_utc": "2024-01-15T14:30:00Z",
                    "article_url": "https://example.com/multi1",
                    "tickers": ["AAPL", "MSFT", "GOOGL"],
                    "description": "Tech stocks surge...",
                    "keywords": ["tech", "rally"],
                    "insights": [
                        {
                            "ticker": "AAPL",
                            "sentiment": "positive",
                            "sentiment_reasoning": "Strong guidance",
                            "sentiment_score": 0.8
                        },
                        {
                            "ticker": "MSFT",
                            "sentiment": "positive",
                            "sentiment_reasoning": "Cloud growth",
                            "sentiment_score": 0.7
                        },
                        {
                            "ticker": "GOOGL",
                            "sentiment": "neutral",
                            "sentiment_reasoning": "Mixed results",
                            "sentiment_score": 0.1
                        }
                    ]
                }
            ]
        }
        mock_request.return_value = multi_ticker_response

        articles = provider.fetch_news_for_ticker("AAPL")

        article = articles[0]
        assert len(article.insights) == 3

        aapl_insight = article.get_insight_for_ticker("AAPL")
        assert aapl_insight.sentiment_score == 0.8

        msft_insight = article.get_insight_for_ticker("MSFT")
        assert msft_insight.sentiment_score == 0.7

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
