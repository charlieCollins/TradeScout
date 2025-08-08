"""
Tests for web scraping components.

These tests are marked as 'integration' because they perform live web requests.
"""

import pytest
from tradescout.web_scraping.investing_com_after_hours_scraper import InvestingComAfterHoursScraper
from tradescout.web_scraping.advfn_after_hours_scraper import ADVFNAfterHoursScraper

@pytest.mark.integration
class TestInvestingComAfterHoursScraper:
    """
    Test suite for the InvestingComAfterHoursScraper.
    """

    def test_initialization(self):
        """Test that the scraper can be initialized."""
        scraper = InvestingComAfterHoursScraper()
        assert scraper is not None
        assert scraper.base_url == "https://www.investing.com/equities/after-hours"

    def test_get_after_hours_gainers_integration(self):
        """
        Integration test for get_after_hours_gainers.
        This test performs a live web request.
        """
        # Arrange
        scraper = InvestingComAfterHoursScraper(headless=True)

        # Act
        gainers = scraper.get_after_hours_gainers(limit=5)

        # Assert
        assert isinstance(gainers, list)

        # This test should pass even if the market is closed and no movers are returned.
        if gainers:
            assert len(gainers) <= 5

            # Check the structure of the first item
            first_gainer = gainers[0]
            assert isinstance(first_gainer, dict)

            expected_keys = [
                "symbol",
                "company_name",
                "regular_close",
                "after_hours_price",
                "after_hours_change",
                "after_hours_change_percent",
                "after_hours_volume",
                "source",
                "timestamp",
                "session",
            ]

            for key in expected_keys:
                assert key in first_gainer

            # Check data types
            assert isinstance(first_gainer["symbol"], str)
            assert isinstance(first_gainer["after_hours_price"], float)
            assert isinstance(first_gainer["after_hours_volume"], int)
            assert first_gainer["source"] == "investing_com_after_hours"

            # Check that gainers are sorted correctly (highest change percent first)
            if len(gainers) > 1:
                assert gainers[0]['after_hours_change_percent'] >= gainers[1]['after_hours_change_percent']


@pytest.mark.integration
class TestADVFNAfterHoursScraper:
    """
    Test suite for the ADVFNAfterHoursScraper.
    """

    def test_get_after_hours_gainers_integration(self):
        """
        Integration test for get_after_hours_gainers on the ADVFN scraper.
        """
        # Arrange
        scraper = ADVFNAfterHoursScraper(exchange='nasdaq', headless=True)

        # Act
        gainers = scraper.get_after_hours_gainers(limit=5)

        # Assert
        assert isinstance(gainers, list)

        if gainers:
            assert len(gainers) <= 5
            first_gainer = gainers[0]
            assert isinstance(first_gainer, dict)

            expected_keys = [
                "symbol", "company_name", "regular_close", "after_hours_price",
                "after_hours_change", "after_hours_change_percent",
                "after_hours_volume", "source", "timestamp", "session"
            ]
            for key in expected_keys:
                assert key in first_gainer

            assert isinstance(first_gainer["symbol"], str)
            assert isinstance(first_gainer["after_hours_price"], float)
            assert isinstance(first_gainer["after_hours_volume"], int)
            assert first_gainer["source"] == "advfn_nasdaq_after_hours"
