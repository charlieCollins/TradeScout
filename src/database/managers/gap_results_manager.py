"""Gap results database manager for storing and querying gap analysis results."""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from models.gap import GapCandidate

logger = logging.getLogger(__name__)


class GapResultsManager:
    """Manages gap_results table for storing gap analysis results.

    This manager does NOT use the BaseManager pattern because gap results
    are not cached entities - they're historical records that we query
    rather than retrieve by ID.
    """

    def __init__(self, db_manager):
        """Initialize gap results manager.

        Args:
            db_manager: Database connection manager
        """
        self.db_manager = db_manager

    def save_gap_result(self, gap_candidate: GapCandidate, analysis_timestamp: datetime) -> Optional[int]:
        """Save a gap candidate result to the database.

        Args:
            gap_candidate: GapCandidate object with all analysis results
            analysis_timestamp: When the analysis was performed

        Returns:
            gap_result_id if successful, None otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO gap_results (
                        asset_id, analysis_timestamp, session_type, trading_date,
                        gap_percentage, gap_direction, gap_type, academic_gap_type,
                        reference_price, current_price, day_open, day_high, day_low, day_close,
                        prevday_close, prevday_high, prevday_low,
                        extended_hours_volume, previous_day_volume, volume_ratio,
                        market_cap, sector,
                        quality_score, quality_tier, catalyst_score, volume_score,
                        gap_size_score, sector_alignment_score, market_alignment_score,
                        passed_gap_filter, passed_volume_filter, passed_market_cap_filter,
                        passed_exhaustion_filter, is_friday_gap,
                        status, rejection_reason,
                        news_count, sentiment_score, has_tier1_catalyst, catalyst_description,
                        min_timestamp, data_freshness_hours
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    gap_candidate.asset_id,
                    analysis_timestamp,
                    gap_candidate.session_type,
                    gap_candidate.trading_date,
                    gap_candidate.gap_percentage,
                    gap_candidate.direction.value if gap_candidate.direction else None,
                    gap_candidate.gap_type,
                    gap_candidate.academic_gap_type,
                    gap_candidate.reference_price,
                    gap_candidate.current_price,
                    gap_candidate.day_open,
                    gap_candidate.day_high,
                    gap_candidate.day_low,
                    gap_candidate.day_close,
                    gap_candidate.prevday_close,
                    gap_candidate.prevday_high,
                    gap_candidate.prevday_low,
                    gap_candidate.extended_hours_volume,
                    gap_candidate.previous_day_volume,
                    gap_candidate.volume_ratio,
                    gap_candidate.market_cap,
                    gap_candidate.sector,
                    gap_candidate.quality_score,
                    gap_candidate.quality_tier,
                    gap_candidate.catalyst_score,
                    gap_candidate.volume_score,
                    gap_candidate.gap_size_score,
                    gap_candidate.sector_alignment_score,
                    gap_candidate.market_alignment_score,
                    gap_candidate.passed_gap_filter,
                    gap_candidate.passed_volume_filter,
                    gap_candidate.passed_market_cap_filter,
                    gap_candidate.passed_exhaustion_filter,
                    gap_candidate.is_friday_gap,
                    gap_candidate.status,
                    gap_candidate.rejection_reason,
                    gap_candidate.news_count,
                    gap_candidate.sentiment_score,
                    gap_candidate.has_tier1_catalyst,
                    gap_candidate.catalyst_description,
                    gap_candidate.min_timestamp,
                    gap_candidate.data_freshness_hours
                ))

                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error saving gap result for asset {gap_candidate.asset_id}: {e}")
            return None

    def save_gap_result_news(self, gap_result_id: int, news_articles: List[Dict[str, Any]]) -> bool:
        """Save news articles associated with a gap result.

        Args:
            gap_result_id: ID of the gap_results record
            news_articles: List of news article dicts with headline, source, published_at, sentiment

        Returns:
            True if successful, False otherwise
        """
        if not news_articles:
            return True

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                for article in news_articles:
                    cursor.execute("""
                        INSERT INTO gap_result_news (
                            gap_result_id, news_headline, news_source,
                            news_published_at, news_sentiment
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        gap_result_id,
                        article.get('headline'),
                        article.get('source'),
                        article.get('published_at'),
                        article.get('sentiment')
                    ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving gap result news for gap_result_id {gap_result_id}: {e}")
            return False

    def get_results_by_date(self, trading_date: date, session_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all gap results for a specific trading date.

        Args:
            trading_date: The trading date to query
            session_type: Optional filter for 'premarket' or 'afterhours'

        Returns:
            List of gap result dictionaries
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if session_type:
                    cursor.execute("""
                        SELECT gr.*, a.symbol, a.name
                        FROM gap_results gr
                        JOIN assets a ON gr.asset_id = a.id
                        WHERE gr.trading_date = ? AND gr.session_type = ?
                        ORDER BY gr.quality_score DESC NULLS LAST, gr.gap_percentage DESC
                    """, (trading_date, session_type))
                else:
                    cursor.execute("""
                        SELECT gr.*, a.symbol, a.name
                        FROM gap_results gr
                        JOIN assets a ON gr.asset_id = a.id
                        WHERE gr.trading_date = ?
                        ORDER BY gr.session_type, gr.quality_score DESC NULLS LAST, gr.gap_percentage DESC
                    """, (trading_date,))

                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Error getting gap results for date {trading_date}: {e}")
            return []

    def get_results_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get gap results filtered by status.

        Args:
            status: Status to filter by ('passed', 'rejected', 'warning')
            limit: Maximum number of results to return

        Returns:
            List of gap result dictionaries
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT gr.*, a.symbol, a.name
                    FROM gap_results gr
                    JOIN assets a ON gr.asset_id = a.id
                    WHERE gr.status = ?
                    ORDER BY gr.analysis_timestamp DESC
                    LIMIT ?
                """, (status, limit))

                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Error getting gap results by status {status}: {e}")
            return []

    def get_results_by_quality_tier(self, quality_tier: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get gap results filtered by quality tier.

        Args:
            quality_tier: Quality tier to filter by ('excellent', 'good', 'fair', 'poor')
            limit: Maximum number of results to return

        Returns:
            List of gap result dictionaries
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT gr.*, a.symbol, a.name
                    FROM gap_results gr
                    JOIN assets a ON gr.asset_id = a.id
                    WHERE gr.quality_tier = ?
                    ORDER BY gr.analysis_timestamp DESC
                    LIMIT ?
                """, (quality_tier, limit))

                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Error getting gap results by quality tier {quality_tier}: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall gap results statistics.

        Returns:
            Dictionary with statistics about gap results
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Total counts
                cursor.execute("SELECT COUNT(*) FROM gap_results")
                total_results = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM gap_results WHERE status = 'passed'")
                passed_results = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM gap_results WHERE status = 'rejected'")
                rejected_results = cursor.fetchone()[0]

                # Quality tier breakdown
                cursor.execute("""
                    SELECT quality_tier, COUNT(*) as count
                    FROM gap_results
                    WHERE quality_tier IS NOT NULL
                    GROUP BY quality_tier
                """)
                quality_tiers = dict(cursor.fetchall())

                # Session breakdown
                cursor.execute("""
                    SELECT session_type, COUNT(*) as count
                    FROM gap_results
                    GROUP BY session_type
                """)
                sessions = dict(cursor.fetchall())

                return {
                    'total_results': total_results,
                    'passed': passed_results,
                    'rejected': rejected_results,
                    'quality_tiers': quality_tiers,
                    'sessions': sessions
                }

        except Exception as e:
            logger.error(f"Error getting gap results statistics: {e}")
            return {}
