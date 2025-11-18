"""Screener Repository - Data access for screener queries.

This repository handles SQL query building and execution for screeners.
All screener SQL logic belongs here, not in the screener engine.
"""

import logging
from typing import List, Dict, Any
from datetime import date
from sqlmodel import Session

logger = logging.getLogger(__name__)


class ScreenerRepository:
    """Repository for screener data queries."""

    def __init__(self, session: Session):
        """Initialize screener repository.

        Args:
            session: SQLModel session for database operations
        """
        self.session = session

    def execute_screener_query(
        self,
        universe: str,
        expected_date: date,
        filters: List[Dict[str, Any]],
        sort: List[Dict[str, Any]],
        limit: int,
        require_recent_trading: bool = True,
        previous_trading_date: date = None
    ) -> List[Dict[str, Any]]:
        """Execute a screener query with filters and sorting.

        Business query: Find assets matching screener criteria.

        Args:
            universe: Universe name to query
            expected_date: Expected data date (for filtering)
            previous_trading_date: Previous trading date (for prevday fallback)
            filters: List of filter conditions
            sort: List of sort specifications
            limit: Maximum number of results
            require_recent_trading: Filter for recent trading activity

        Returns:
            List of matching assets with price data
        """
        # Build SELECT clause with all available fields (including fallback fields)
        select_fields = [
            "a.symbol",
            "a.name",
            "ap.prevday_close",
            "ap.prevday_volume",
            "pdp.day_close as fallback_prevday_close",
            "pdp.day_volume as fallback_prevday_volume",
            "ap.day_open",
            "ap.day_close",
            "ap.day_volume",
            "ap.min_close",
            "ap.min_volume",
            "ap.min_accumulated_volume",
            "ap.min_timestamp",
        ]

        expected_date_str = expected_date.strftime('%Y-%m-%d')

        # Build query with optional prev_day JOIN for fallback
        if previous_trading_date:
            previous_date_str = previous_trading_date.strftime('%Y-%m-%d')
            query = f"""
            WITH latest_prices AS (
                SELECT
                    asset_id,
                    prevday_close,
                    prevday_volume,
                    day_open,
                    day_close,
                    day_volume,
                    min_close,
                    min_volume,
                    min_accumulated_volume,
                    min_timestamp,
                    provider_updated_at,
                    trade_date,
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{expected_date_str}'
            ),
            prev_day_prices AS (
                SELECT
                    asset_id,
                    day_close,
                    day_volume,
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{previous_date_str}'
            )
            SELECT {', '.join(select_fields)}
            FROM assets a
            JOIN universe_memberships um ON a.id = um.asset_id
            JOIN universes u ON um.universe_id = u.id
            JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
            LEFT JOIN prev_day_prices pdp ON a.id = pdp.asset_id AND pdp.rn = 1
            WHERE u.name = '{universe}'
            """
        else:
            # No fallback - original behavior
            query = f"""
            WITH latest_prices AS (
                SELECT
                    asset_id,
                    prevday_close,
                    prevday_volume,
                    day_open,
                    day_close,
                    day_volume,
                    min_close,
                    min_volume,
                    min_accumulated_volume,
                    min_timestamp,
                    provider_updated_at,
                    trade_date,
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{expected_date_str}'
            )
            SELECT a.symbol, a.name, ap.prevday_close, ap.prevday_volume,
                   ap.day_open, ap.day_close, ap.day_volume,
                   ap.min_close, ap.min_volume, ap.min_accumulated_volume, ap.min_timestamp
            FROM assets a
            JOIN universe_memberships um ON a.id = um.asset_id
            JOIN universes u ON um.universe_id = u.id
            JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
            WHERE u.name = '{universe}'
            """

        # Add require_recent_trading filter
        if require_recent_trading:
            query += " AND ap.provider_updated_at > 0"

        # Add custom filters
        for filter_def in filters:
            field = filter_def["field"]
            operator = filter_def["operator"]
            value = filter_def["value"]

            # Add WHERE clause
            if isinstance(value, list):
                value_str = f"({','.join(map(str, value))})"
                query += f" AND {field} {operator} {value_str}"
            elif value is None and operator in ["IS NOT NULL", "IS NULL"]:
                query += f" AND {field} {operator}"
            else:
                query += f" AND {field} {operator} {value}"

        # Add sorting
        if sort:
            order_by_parts = []
            for sort_def in sort:
                field = sort_def["field"]
                direction = sort_def.get("direction", "desc").upper()
                order_by_parts.append(f"{field} {direction}")

            if order_by_parts:
                query += f" ORDER BY {', '.join(order_by_parts)}"

        # Add limit
        query += f" LIMIT {limit}"

        # Execute query (wrap in text() for SQLModel)
        from sqlmodel import text
        result = self.session.exec(text(query))
        rows = result.all()

        # Convert rows to dictionaries
        results = []
        for row in rows:
            # SQLModel returns Row objects, convert to dict
            row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(select_fields, row))
            results.append(row_dict)

        # Apply prevday fallback logic ONLY if previous_trading_date was provided
        if previous_trading_date:
            snapshot_count = 0
            fallback_count = 0
            missing_count = 0

            for row in results:
                if row.get('prevday_close') is not None:
                    # Snapshot data - use as-is
                    snapshot_count += 1
                elif row.get('fallback_prevday_close') is not None:
                    # Backfilled data - use fallback from previous day
                    row['prevday_close'] = row['fallback_prevday_close']
                    row['prevday_volume'] = row.get('fallback_prevday_volume')
                    fallback_count += 1
                else:
                    # Missing both
                    missing_count += 1

                # Remove fallback fields from final output
                row.pop('fallback_prevday_close', None)
                row.pop('fallback_prevday_volume', None)

            # Log strategy usage
            if fallback_count > 0 or missing_count > 0:
                logger.info(
                    f"Prevday data sources: {snapshot_count} snapshot, "
                    f"{fallback_count} fallback to prev day, {missing_count} missing both"
                )

        return results

    def count_excluded_by_date(self, universe_name: str, expected_date: date) -> int:
        """Count assets excluded due to date mismatch.

        Business query: Screener validation - count assets filtered out by date.

        Args:
            universe_name: Universe to query
            expected_date: Expected data date

        Returns:
            Number of assets with price data but not matching expected date
        """
        from sqlmodel import select, func
        from models.sqlmodel.asset_sqlmodel import AssetSQLModel
        from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel
        from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel

        # Count total assets with any price data
        total_statement = (
            select(func.count(func.distinct(AssetSQLModel.id)))
            .select_from(AssetSQLModel)
            .join(UniverseMembershipSQLModel, AssetSQLModel.id == UniverseMembershipSQLModel.asset_id)
            .join(UniverseSQLModel, UniverseMembershipSQLModel.universe_id == UniverseSQLModel.id)
            .join(AssetPriceSQLModel, AssetSQLModel.id == AssetPriceSQLModel.asset_id)
            .where(UniverseSQLModel.name == universe_name)
        )

        # Count assets with price data matching expected date
        matching_statement = (
            select(func.count(func.distinct(AssetSQLModel.id)))
            .select_from(AssetSQLModel)
            .join(UniverseMembershipSQLModel, AssetSQLModel.id == UniverseMembershipSQLModel.asset_id)
            .join(UniverseSQLModel, UniverseMembershipSQLModel.universe_id == UniverseSQLModel.id)
            .join(AssetPriceSQLModel, AssetSQLModel.id == AssetPriceSQLModel.asset_id)
            .where(UniverseSQLModel.name == universe_name)
            .where(AssetPriceSQLModel.trade_date == expected_date)
        )

        total = self.session.exec(total_statement).one()
        matching = self.session.exec(matching_statement).one()

        return total - matching

    def count_assets_with_reference_price(
        self,
        universe: str,
        expected_date: date,
        reference_field: str,
        previous_trading_date: date = None
    ) -> int:
        """Count assets with non-NULL reference price data (including fallback).

        Business query: Check if reference price data is available for screener.
        Checks both snapshot prevday_close AND previous day's day_close as fallback.

        Args:
            universe: Universe name
            expected_date: Expected data date
            previous_trading_date: Previous trading date (for fallback)
            reference_field: Field name to check (e.g., 'prevday_close')

        Returns:
            Number of assets with non-NULL reference price (from either source)
        """
        expected_date_str = expected_date.strftime('%Y-%m-%d')

        if previous_trading_date:
            previous_date_str = previous_trading_date.strftime('%Y-%m-%d')
            query = f"""
            WITH latest_prices AS (
                SELECT
                    asset_id,
                    {reference_field},
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{expected_date_str}'
            ),
            prev_day_prices AS (
                SELECT
                    asset_id,
                    day_close,
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{previous_date_str}'
            )
            SELECT COUNT(DISTINCT a.id)
            FROM assets a
            JOIN universe_memberships um ON a.id = um.asset_id
            JOIN universes u ON um.universe_id = u.id
            JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
            LEFT JOIN prev_day_prices pdp ON a.id = pdp.asset_id AND pdp.rn = 1
            WHERE u.name = '{universe}'
              AND (ap.{reference_field} IS NOT NULL OR pdp.day_close IS NOT NULL)
            """
        else:
            # Original behavior - only check reference_field
            query = f"""
            WITH latest_prices AS (
                SELECT
                    asset_id,
                    {reference_field},
                    ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
                FROM asset_prices
                WHERE trade_date = '{expected_date_str}'
            )
            SELECT COUNT(DISTINCT a.id)
            FROM assets a
            JOIN universe_memberships um ON a.id = um.asset_id
            JOIN universes u ON um.universe_id = u.id
            JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
            WHERE u.name = '{universe}'
              AND ap.{reference_field} IS NOT NULL
            """

        from sqlmodel import text
        result = self.session.exec(text(query))
        row = result.one()

        # Extract scalar value from Row object
        count = row[0] if hasattr(row, '__getitem__') else row

        return count
