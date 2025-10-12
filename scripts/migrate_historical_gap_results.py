#!/usr/bin/env python3
"""Migrate historical gap candidates from GAP_RESULTS.md to database."""

import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.database_manager import DatabaseManager
from database.managers import AssetManager


def insert_gap_result(cursor, asset_id, analysis_ts, session, trade_date, gap_pct, vol_ratio, market_cap, volume, rejection):
    """Insert a gap result record."""
    cursor.execute("""
        INSERT INTO gap_results (
            asset_id, analysis_timestamp, session_type, trading_date,
            gap_percentage, gap_direction,
            reference_price, current_price, prevday_close,
            extended_hours_volume, volume_ratio, market_cap,
            passed_gap_filter, passed_volume_filter, passed_market_cap_filter,
            passed_exhaustion_filter, is_friday_gap,
            status, rejection_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        asset_id, analysis_ts, session, trade_date,
        gap_pct, "up", 0.0, 0.0, 0.0,
        volume, vol_ratio, market_cap,
        True, False, True, True, False,
        "rejected", rejection
    ))
    return cursor.lastrowid


def main():
    print("=" * 60)
    print("Historical Gap Results Migration")
    print("=" * 60)

    db_manager = DatabaseManager()
    asset_manager = AssetManager(db_manager, None)

    # Historical candidates from GAP_RESULTS.md
    oct_7_ah = [
        ("QS", 5.94, 8.09e9, 0.33, 2547602),
        ("TWST", 4.43, 1.85e9, 0.023, 8611),
        ("CAI", 4.40, 8.36e9, 0.003, 401),
        ("QURE", 4.28, 3.36e9, 0.17, 94540),
        ("BRKR", 4.17, 5.28e9, 0.076, 39956),
    ]

    oct_7_pm = [
        ("BITF", 16.47, 1.62e9, 0.0, 29000),
        ("DGNX", 12.32, 3.19e9, 0.02, 2000),
        ("AMKR", 10.60, 7.33e9, 0.0, 101),
        ("JHX", 9.91, 11.42e9, 0.0, 900),
        ("HIVE", 9.16, 1.01e9, 0.0, 1900),
        ("AMD", 3.77, 275e9, 0.0, 4600),
        ("IBM", 4.69, 267e9, 0.0, 1000),
    ]

    oct_6_pm = [
        ("CMA", 13.3, 11e9, 0.010, 2000),
        ("PLUG", 17.3, None, 0.001, 62000),
        ("LITM", 13.3, None, 0.151, 58000),
        ("RR", 10.6, None, 0.001, 22000),
    ]

    total = 0
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Oct 7 After-Hours
        print("\nMigrating 2025-10-07 After-Hours...")
        ts = datetime(2025, 10, 7, 19, 15)
        for symbol, gap, mcap, ratio, vol in oct_7_ah:
            asset = asset_manager.get_entity_from_database(symbol)
            if asset:
                rid = insert_gap_result(cursor, asset.id, ts, "afterhours", date(2025, 10, 7), gap, ratio, mcap, vol, "Volume < 1.5x")
                print(f"  ✅ {symbol}: gap_result_id={rid}")
                total += 1
            else:
                print(f"  ⚠️  {symbol}: Not found in assets")

        # Oct 7 Premarket
        print("\nMigrating 2025-10-07 Premarket...")
        ts = datetime(2025, 10, 7, 8, 30)
        for symbol, gap, mcap, ratio, vol in oct_7_pm:
            asset = asset_manager.get_entity_from_database(symbol)
            if asset:
                rid = insert_gap_result(cursor, asset.id, ts, "premarket", date(2025, 10, 7), gap, ratio, mcap, vol, "Volume < 1.5x")
                print(f"  ✅ {symbol}: gap_result_id={rid}")
                total += 1
            else:
                print(f"  ⚠️  {symbol}: Not found in assets")

        # Oct 6 Premarket
        print("\nMigrating 2025-10-06 Premarket...")
        ts = datetime(2025, 10, 6, 9, 0)
        for symbol, gap, mcap, ratio, vol in oct_6_pm:
            asset = asset_manager.get_entity_from_database(symbol)
            if asset:
                rid = insert_gap_result(cursor, asset.id, ts, "premarket", date(2025, 10, 6), gap, ratio, mcap, vol, "Volume < 1.5x")
                print(f"  ✅ {symbol}: gap_result_id={rid}")
                total += 1
            else:
                print(f"  ⚠️  {symbol}: Not found in assets")

        conn.commit()

    print("\n" + "=" * 60)
    print(f"✅ Migration complete: {total} gap results saved")
    print("=" * 60)

    # Show stats
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gap_results")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM gap_results WHERE status='rejected'")
        rejected = cursor.fetchone()[0]
        print(f"\nDatabase: {count} total results, {rejected} rejected")


if __name__ == "__main__":
    main()
