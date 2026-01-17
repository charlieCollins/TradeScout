"""AssetPrice Repository - Business-focused data access for price/snapshot data.

This repository provides domain-specific operations for AssetPrice data.
It wraps the DAO layer (AssetPriceSQLModel) with business queries for gap trading.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlmodel import Session, select, desc
from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel

logger = logging.getLogger(__name__)


class AssetPriceRepository:
    """Repository for AssetPrice business operations.

    This layer provides business-focused data access for price/snapshot data.
    Critical for gap trading analysis which compares prev_close to current prices.

    Responsibilities:
    - Latest price queries (for gap analysis)
    - Historical price queries (by date range)
    - Price persistence
    - Gap calculations
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLModel session for database operations
        """
        self.session = session

    # ============================================================================
    # LATEST PRICE QUERIES (Critical for Gap Trading)
    # ============================================================================

    def get_latest_by_symbol(self, symbol: str) -> Optional[AssetPriceSQLModel]:
        """Get most recent price data for a symbol.

        Business query: Used by gap analysis to get current snapshot.

        Orders by provider_updated_at (when Polygon says data is from) first,
        then updated_at (when we inserted it) as tiebreaker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Most recent AssetPrice or None
        """
        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.symbol == symbol.upper()
        ).order_by(
            desc(AssetPriceSQLModel.provider_updated_at),
            desc(AssetPriceSQLModel.updated_at)
        ).limit(1)

        return self.session.exec(statement).first()

    def get_latest_for_symbols(
        self,
        symbols: List[str]
    ) -> List[AssetPriceSQLModel]:
        """Get most recent prices for multiple symbols.

        Business query: Batch query for gap screeners.

        Args:
            symbols: List of stock symbols

        Returns:
            List of most recent prices (one per symbol)
        """
        # For each symbol, get the most recent record
        # This is a suboptimal query but works for now
        # TODO: Optimize with window functions
        results = []
        for symbol in symbols:
            price = self.get_latest_by_symbol(symbol)
            if price:
                results.append(price)

        return results

    # ============================================================================
    # HISTORICAL QUERIES
    # ============================================================================

    def get_by_trade_date(
        self,
        symbol: str,
        trade_date: date
    ) -> Optional[AssetPriceSQLModel]:
        """Get price data for a specific trade date.

        Args:
            symbol: Stock symbol
            trade_date: Trading date

        Returns:
            AssetPrice for that date or None
        """
        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.symbol == symbol.upper(),
            AssetPriceSQLModel.trade_date == trade_date
        ).order_by(desc(AssetPriceSQLModel.updated_at)).limit(1)

        return self.session.exec(statement).first()

    def find_by_date_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[AssetPriceSQLModel]:
        """Get price data for a date range.

        Args:
            symbol: Stock symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of prices ordered by date descending
        """
        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.symbol == symbol.upper(),
            AssetPriceSQLModel.trade_date >= start_date,
            AssetPriceSQLModel.trade_date <= end_date
        ).order_by(desc(AssetPriceSQLModel.trade_date))

        return list(self.session.exec(statement).all())

    def find_recent(
        self,
        symbol: str,
        days: int = 30
    ) -> List[AssetPriceSQLModel]:
        """Get recent price data for a symbol.

        Args:
            symbol: Stock symbol
            days: Number of days to look back (default: 30)

        Returns:
            List of recent prices ordered by date descending
        """
        cutoff_date = date.today() - timedelta(days=days)

        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.symbol == symbol.upper(),
            AssetPriceSQLModel.trade_date >= cutoff_date
        ).order_by(desc(AssetPriceSQLModel.trade_date))

        return list(self.session.exec(statement).all())

    # ============================================================================
    # GAP ANALYSIS QUERIES
    # ============================================================================

    def find_with_gaps(
        self,
        min_gap_percent: float = 2.0,
        trade_date: Optional[date] = None
    ) -> List[AssetPriceSQLModel]:
        """Find assets with significant gaps.

        Business query: Core gap trading screener.

        Args:
            min_gap_percent: Minimum gap percentage (default: 2%)
            trade_date: Specific date to check (default: today)

        Returns:
            List of assets with gaps meeting criteria
        """
        if trade_date is None:
            trade_date = date.today()

        # Get all prices for the date
        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.trade_date == trade_date,
            AssetPriceSQLModel.prevday_close.is_not(None),  # type: ignore
            AssetPriceSQLModel.day_open.is_not(None)  # type: ignore
        )

        all_prices = self.session.exec(statement).all()

        # Filter by gap percent (must calculate in Python for now)
        # TODO: Move to SQL if performance becomes an issue
        results = []
        for price in all_prices:
            gap_pct = price.gap_percent
            if gap_pct is not None and abs(gap_pct) >= min_gap_percent:
                results.append(price)

        return results

    # ============================================================================
    # PERSISTENCE
    # ============================================================================

    def save(self, price: AssetPriceSQLModel) -> AssetPriceSQLModel:
        """Persist price data to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            price: AssetPrice to persist

        Returns:
            Persisted price
        """
        self.session.add(price)
        self.session.commit()
        self.session.refresh(price)
        logger.debug(f"Saved price for {price.symbol} on {price.trade_date}")
        return price

    def bulk_save(self, prices: List[AssetPriceSQLModel]) -> int:
        """Bulk persist multiple prices - only insert new provider_updated_at values.

        Checks for existing records by (asset_id, provider_id, provider_updated_at).
        If a record with that exact provider_updated_at exists, skip it (data hasn't changed).
        Only insert records with new provider_updated_at values.

        Args:
            prices: List of prices to persist

        Returns:
            Number of prices actually inserted (skips existing)
        """
        if not prices:
            return 0

        # Filter out any records with provider_updated_at = 0 (invalid/missing data)
        valid_prices = [p for p in prices if p.provider_updated_at and p.provider_updated_at != 0]
        rejected_count = len(prices) - len(valid_prices)
        if rejected_count > 0:
            logger.warning(f"Rejected {rejected_count} prices with provider_updated_at=0")

        if not valid_prices:
            return 0

        # Deduplicate incoming batch - keep only the last occurrence of each unique key
        # This handles cases where the same asset appears multiple times in the batch
        unique_prices = {}
        for price in valid_prices:
            key = (price.asset_id, price.provider_id, price.provider_updated_at)
            unique_prices[key] = price  # Last one wins if duplicates exist

        prices_to_check = list(unique_prices.values())
        logger.debug(f"Deduped {len(valid_prices)} prices to {len(prices_to_check)} unique records")

        # Get all existing (asset_id, provider_id, provider_updated_at) tuples for these assets
        # Query using IN clauses to avoid SQLite expression tree limits
        asset_ids = list(set(p.asset_id for p in prices_to_check))
        provider_ids = list(set(p.provider_id for p in prices_to_check))

        statement = select(
            AssetPriceSQLModel.asset_id,
            AssetPriceSQLModel.provider_id,
            AssetPriceSQLModel.provider_updated_at
        ).where(
            AssetPriceSQLModel.asset_id.in_(asset_ids),
            AssetPriceSQLModel.provider_id.in_(provider_ids)
        )

        existing_records = self.session.exec(statement).all()

        # Build set of (asset_id, provider_id, provider_updated_at) tuples that already exist
        existing_keys = {
            (rec[0], rec[1], rec[2]) for rec in existing_records
        }

        # Only insert prices that don't already exist
        inserted_count = 0
        for price in prices_to_check:
            key = (price.asset_id, price.provider_id, price.provider_updated_at)
            if key not in existing_keys:
                # This exact record doesn't exist yet, insert it
                self.session.add(price)
                inserted_count += 1

        if inserted_count > 0:
            self.session.commit()
            logger.debug(f"Bulk saved {inserted_count} new prices (skipped {len(prices_to_check) - inserted_count} existing)")
        else:
            logger.debug(f"No new prices to save (all {len(prices_to_check)} records already exist)")
        return inserted_count

    def bulk_upsert(self, prices: List[AssetPriceSQLModel], force_refresh: bool = False) -> dict:
        """Bulk upsert prices - insert new or update existing based on (asset_id, trade_date).

        Business rules:
        - Normal mode (force_refresh=False):
          * INSERT if record doesn't exist
          * UPDATE if record exists AND new data is newer (provider_updated_at)
          * SKIP if record exists AND new data is older/same

        - Force mode (force_refresh=True):
          * DELETE all existing records for these (asset_id, trade_date) combinations
          * INSERT all new records (complete refresh with latest API data)

        Args:
            prices: List of prices to upsert
            force_refresh: If True, delete existing and insert fresh. If False, smart upsert.

        Returns:
            Dictionary with counts: {'inserted': int, 'updated': int, 'skipped': int, 'deleted': int}
        """
        if not prices:
            return {'inserted': 0, 'updated': 0, 'skipped': 0, 'deleted': 0}

        # Filter out invalid records
        valid_prices = [p for p in prices if p.provider_updated_at and p.provider_updated_at != 0]
        if not valid_prices:
            return {'inserted': 0, 'updated': 0, 'skipped': 0, 'deleted': 0}

        deleted_count = 0
        inserted_count = 0
        updated_count = 0
        skipped_count = 0

        if force_refresh:
            # FORCE MODE: Delete existing records, then insert fresh
            # Build list of (asset_id, trade_date) tuples to delete
            keys_to_delete = [(p.asset_id, p.trade_date) for p in valid_prices]

            # Delete all existing records for these keys
            for asset_id, trade_date in keys_to_delete:
                statement = select(AssetPriceSQLModel).where(
                    AssetPriceSQLModel.asset_id == asset_id,
                    AssetPriceSQLModel.trade_date == trade_date
                )
                existing = self.session.exec(statement).first()
                if existing:
                    self.session.delete(existing)
                    deleted_count += 1

            # Commit deletes
            if deleted_count > 0:
                self.session.commit()
                logger.debug(f"Force refresh: deleted {deleted_count} existing records")

            # Insert all fresh records
            for price in valid_prices:
                self.session.add(price)
                inserted_count += 1

            self.session.commit()
            logger.debug(f"Force refresh: inserted {inserted_count} fresh records")

        else:
            # NORMAL MODE: Smart upsert with timestamp checking
            for price in valid_prices:
                # Check if record exists for this (asset_id, trade_date)
                statement = select(AssetPriceSQLModel).where(
                    AssetPriceSQLModel.asset_id == price.asset_id,
                    AssetPriceSQLModel.trade_date == price.trade_date
                )
                existing = self.session.exec(statement).first()

                if existing:
                    # Record exists - only update if new data is newer
                    if price.provider_updated_at > existing.provider_updated_at:
                        # Update existing record
                        existing.provider_id = price.provider_id
                        existing.provider_updated_at = price.provider_updated_at
                        existing.symbol = price.symbol
                        existing.updated_at = price.updated_at
                        existing.prevday_open = price.prevday_open
                        existing.prevday_high = price.prevday_high
                        existing.prevday_low = price.prevday_low
                        existing.prevday_close = price.prevday_close
                        existing.prevday_volume = price.prevday_volume
                        existing.prevday_vwap = price.prevday_vwap
                        existing.day_open = price.day_open
                        existing.day_high = price.day_high
                        existing.day_low = price.day_low
                        existing.day_close = price.day_close
                        existing.day_volume = price.day_volume
                        existing.day_vwap = price.day_vwap
                        existing.min_timestamp = price.min_timestamp
                        existing.min_open = price.min_open
                        existing.min_high = price.min_high
                        existing.min_low = price.min_low
                        existing.min_close = price.min_close
                        existing.min_volume = price.min_volume
                        existing.min_vwap = price.min_vwap
                        existing.min_accumulated_volume = price.min_accumulated_volume
                        existing.min_num_trades = price.min_num_trades
                        self.session.add(existing)
                        updated_count += 1
                    else:
                        # Skip - existing data is newer or same
                        skipped_count += 1
                        logger.debug(
                            f"Skipping {price.symbol} on {price.trade_date} - "
                            f"existing data is newer ({existing.provider_updated_at} >= {price.provider_updated_at})"
                        )
                else:
                    # Insert new record
                    self.session.add(price)
                    inserted_count += 1

            self.session.commit()
            logger.debug(f"Smart upsert: {inserted_count} inserts, {updated_count} updates, {skipped_count} skipped")

        return {
            'inserted': inserted_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'deleted': deleted_count
        }

    def delete(self, price: AssetPriceSQLModel) -> None:
        """Delete price from database.

        Args:
            price: Price to delete
        """
        self.session.delete(price)
        self.session.commit()
        logger.debug(f"Deleted price for {price.symbol} on {price.trade_date}")

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def count_by_symbol(self, symbol: str) -> int:
        """Count price records for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Count of price records
        """
        from sqlmodel import func
        statement = select(func.count(AssetPriceSQLModel.id)).where(
            AssetPriceSQLModel.symbol == symbol.upper()
        )
        return self.session.exec(statement).one() or 0

    def count_by_date(self, trade_date: date) -> int:
        """Count price records for a specific date.

        Args:
            trade_date: Trading date

        Returns:
            Count of price records
        """
        from sqlmodel import func
        statement = select(func.count(AssetPriceSQLModel.id)).where(
            AssetPriceSQLModel.trade_date == trade_date
        )
        return self.session.exec(statement).one() or 0

    def count_all(self) -> int:
        """Count total number of price records across all symbols.

        Returns:
            Total count of price records
        """
        from sqlmodel import func

        statement = select(func.count(AssetPriceSQLModel.id))
        return self.session.exec(statement).one()

    def get_date_range(self, symbol: str) -> tuple[Optional[date], Optional[date]]:
        """Get date range for a symbol's price data.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (earliest_date, latest_date) or (None, None) if no data
        """
        statement = select(
            AssetPriceSQLModel.trade_date
        ).where(
            AssetPriceSQLModel.symbol == symbol.upper()
        ).order_by(AssetPriceSQLModel.trade_date)

        dates = list(self.session.exec(statement).all())

        if not dates:
            return None, None

        return dates[0], dates[-1]

    def get_last_update_time(self) -> Optional[datetime]:
        """Get the timestamp of the most recent price update across all symbols.

        Business query: Used to check data freshness for gap analysis.

        Returns:
            Most recent updated_at timestamp or None if no price data
        """
        statement = select(AssetPriceSQLModel.updated_at).order_by(
            desc(AssetPriceSQLModel.updated_at)
        ).limit(1)

        result = self.session.exec(statement).first()
        return result if result else None

    def get_latest_by_asset_id(self, asset_id: int) -> Optional[AssetPriceSQLModel]:
        """Get most recent price for an asset.

        Business query: Validation commands need latest price for specific asset.

        Args:
            asset_id: Asset database ID

        Returns:
            Most recent AssetPriceSQLModel for this asset, or None
        """
        statement = select(AssetPriceSQLModel).where(
            AssetPriceSQLModel.asset_id == asset_id
        ).order_by(
            desc(AssetPriceSQLModel.provider_updated_at),
            desc(AssetPriceSQLModel.updated_at)
        ).limit(1)

        return self.session.exec(statement).first()

    def get_random_assets_with_prices(self, limit: int = 10) -> list[tuple[str, int, int]]:
        """Get random assets that have recent price data.

        Business query: Validation commands need random sample for testing.

        Args:
            limit: Number of random assets to return (default: 10)

        Returns:
            List of tuples: (symbol, asset_id, latest_asset_price_id)
        """
        from models.sqlmodel.asset_sqlmodel import AssetSQLModel
        from sqlmodel import func

        # Subquery to get latest price IDs per asset
        subquery = (
            select(
                AssetPriceSQLModel.asset_id,
                func.max(AssetPriceSQLModel.id).label('max_id')
            )
            .group_by(AssetPriceSQLModel.asset_id)
            .subquery()
        )

        # Main query joining assets with their latest prices
        statement = (
            select(
                AssetSQLModel.symbol,
                AssetPriceSQLModel.asset_id,
                AssetPriceSQLModel.id
            )
            .select_from(AssetPriceSQLModel)
            .join(AssetSQLModel, AssetPriceSQLModel.asset_id == AssetSQLModel.id)
            .join(subquery, AssetPriceSQLModel.id == subquery.c.max_id)
            .where(
                (AssetPriceSQLModel.min_accumulated_volume > 0) |
                (AssetPriceSQLModel.day_volume > 0) |
                (AssetPriceSQLModel.prevday_volume > 0)
            )
            .order_by(func.random())
            .limit(limit)
        )

        results = self.session.exec(statement).all()
        return [(row[0], row[1], row[2]) for row in results]

    def get_latest_price_ids_for_symbols(self, symbols: list[str]) -> list[tuple[str, int, int]]:
        """Get latest price IDs for specific symbols.

        Business query: Validation commands need latest prices for test symbols.

        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'NVDA'])

        Returns:
            List of tuples: (symbol, asset_id, latest_asset_price_id)
        """
        if not symbols:
            return []

        from models.sqlmodel.asset_sqlmodel import AssetSQLModel
        from sqlmodel import func

        # Subquery to get latest price IDs per asset
        subquery = (
            select(
                AssetPriceSQLModel.asset_id,
                func.max(AssetPriceSQLModel.id).label('max_id')
            )
            .group_by(AssetPriceSQLModel.asset_id)
            .subquery()
        )

        # Main query
        statement = (
            select(
                AssetSQLModel.symbol,
                AssetPriceSQLModel.asset_id,
                AssetPriceSQLModel.id
            )
            .select_from(AssetSQLModel)
            .join(AssetPriceSQLModel, AssetSQLModel.id == AssetPriceSQLModel.asset_id)
            .join(subquery, AssetPriceSQLModel.id == subquery.c.max_id)
            .where(AssetSQLModel.symbol.in_(symbols))
        )

        results = self.session.exec(statement).all()
        return [(row[0], row[1], row[2]) for row in results]

    def get_data_date_summary(self, sample_size: int = 100) -> Dict[str, Any]:
        """Get summary of what trade_dates exist in asset_prices table.

        Business query: Data validation - shows what date(s) the price data is actually from.
        Used to compare against expected data date from MarketContext.

        Args:
            sample_size: Number of random records to sample (default 100)

        Returns:
            Dictionary with:
            - has_data: bool (any data exists)
            - total_records: int
            - unique_dates: List[date] (sorted, most recent first)
            - min_date: Optional[date]
            - max_date: Optional[date]
            - is_uniform: bool (all sampled records have same date)
        """
        from sqlmodel import func

        # Check if any data exists
        count_statement = select(func.count(AssetPriceSQLModel.id))
        total_records = self.session.exec(count_statement).one()

        if total_records == 0:
            return {
                "has_data": False,
                "total_records": 0,
                "unique_dates": [],
                "min_date": None,
                "max_date": None,
                "is_uniform": True
            }

        # Get unique dates from a sample of records
        # Use ORDER BY RANDOM() to get a random sample
        sample_statement = (
            select(AssetPriceSQLModel.trade_date)
            .order_by(func.random())
            .limit(sample_size)
        )
        sample_dates = list(self.session.exec(sample_statement).all())

        # Get overall min/max dates
        date_range_statement = select(
            func.min(AssetPriceSQLModel.trade_date).label('min_date'),
            func.max(AssetPriceSQLModel.trade_date).label('max_date')
        )
        date_range_result = self.session.exec(date_range_statement).first()
        min_date = date_range_result[0] if date_range_result else None
        max_date = date_range_result[1] if date_range_result else None

        # Get unique dates from sample, sorted most recent first
        unique_dates = sorted(set(sample_dates), reverse=True)

        # Check if all sampled dates are the same (uniform data)
        is_uniform = len(unique_dates) == 1

        return {
            "has_data": True,
            "total_records": total_records,
            "unique_dates": unique_dates,
            "min_date": min_date,
            "max_date": max_date,
            "is_uniform": is_uniform
        }
