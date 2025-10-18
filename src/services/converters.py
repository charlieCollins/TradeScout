"""SQLModel to Dataclass Converters.

This module provides converter functions to transform SQLModel objects
(persistence layer) to dataclass objects (domain layer).

Architecture:
- Repository returns SQLModel
- Service uses these converters to transform SQLModel -> dataclass
- Service returns dataclass to command layer
- Command layer never sees SQLModel
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.dataclass.asset import Asset
    from models.dataclass.market import Market
    from models.dataclass.price import AssetPrice
    from models.dataclass.universe import UniverseMembership
    from models.dataclass.sentiment_event import SentimentEvent
    from models.dataclass.fed_data import FedData


def convert_asset_sqlmodel_to_dataclass(sqlmodel: "AssetSQLModel") -> "Asset":
    """Convert AssetSQLModel to Asset dataclass.

    Args:
        sqlmodel: AssetSQLModel from repository

    Returns:
        Asset dataclass for service/command layers
    """
    from models.dataclass.asset import Asset, AssetType, AssetClass

    return Asset(
        id=sqlmodel.id,
        symbol=sqlmodel.symbol,
        name=sqlmodel.name,
        asset_type=AssetType(sqlmodel.asset_type),
        asset_class=AssetClass(sqlmodel.asset_class),
        market_id=sqlmodel.market_id,
        currency=sqlmodel.currency,
        lot_size=sqlmodel.lot_size,
        tick_size=sqlmodel.tick_size,
        is_active=sqlmodel.is_active,
        is_delisted=sqlmodel.is_delisted,
        listing_date=sqlmodel.listing_date,
        delisting_date=sqlmodel.delisting_date,
        provider_id=sqlmodel.provider_id,
        created_at=sqlmodel.created_at,
        updated_at=sqlmodel.updated_at
    )


def convert_market_sqlmodel_to_dataclass(sqlmodel: "MarketSQLModel") -> "Market":
    """Convert MarketSQLModel to Market dataclass.

    Args:
        sqlmodel: MarketSQLModel from repository

    Returns:
        Market dataclass for service/command layers
    """
    from models.dataclass.market import Market

    return Market(
        id=sqlmodel.id,
        code=sqlmodel.code,
        name=sqlmodel.name,
        country=sqlmodel.country,
        timezone=sqlmodel.timezone,
        currency=sqlmodel.currency,
        premarket_start_time=sqlmodel.premarket_start_time,
        premarket_end_time=sqlmodel.premarket_end_time,
        regular_open_time=sqlmodel.regular_open_time,
        regular_close_time=sqlmodel.regular_close_time,
        afterhours_start_time=sqlmodel.afterhours_start_time,
        afterhours_end_time=sqlmodel.afterhours_end_time,
        is_active=sqlmodel.is_active,
        created_at=sqlmodel.created_at,
        updated_at=sqlmodel.updated_at
    )


def convert_asset_price_sqlmodel_to_dataclass(sqlmodel: "AssetPriceSQLModel") -> "AssetPrice":
    """Convert AssetPriceSQLModel to AssetPrice dataclass.

    Args:
        sqlmodel: AssetPriceSQLModel from repository

    Returns:
        AssetPrice dataclass for service/command layers
    """
    from models.dataclass.price import AssetPrice

    return AssetPrice(
        id=sqlmodel.id,
        asset_id=sqlmodel.asset_id,
        symbol=sqlmodel.symbol,
        provider_id=sqlmodel.provider_id,
        provider_updated_at=sqlmodel.provider_updated_at,
        trade_date=sqlmodel.trade_date,
        updated_at=sqlmodel.updated_at,
        prevday_open=sqlmodel.prevday_open,
        prevday_high=sqlmodel.prevday_high,
        prevday_low=sqlmodel.prevday_low,
        prevday_close=sqlmodel.prevday_close,
        prevday_volume=sqlmodel.prevday_volume,
        prevday_vwap=sqlmodel.prevday_vwap,
        day_open=sqlmodel.day_open,
        day_high=sqlmodel.day_high,
        day_low=sqlmodel.day_low,
        day_close=sqlmodel.day_close,
        day_volume=sqlmodel.day_volume,
        day_vwap=sqlmodel.day_vwap,
        min_timestamp=sqlmodel.min_timestamp,
        min_open=sqlmodel.min_open,
        min_high=sqlmodel.min_high,
        min_low=sqlmodel.min_low,
        min_close=sqlmodel.min_close,
        min_volume=sqlmodel.min_volume,
        min_vwap=sqlmodel.min_vwap,
        min_accumulated_volume=sqlmodel.min_accumulated_volume,
        min_num_trades=sqlmodel.min_num_trades
    )


def convert_universe_membership_sqlmodel_to_dataclass(sqlmodel: "UniverseMembershipSQLModel") -> "UniverseMembership":
    """Convert UniverseMembershipSQLModel to UniverseMembership dataclass.

    Args:
        sqlmodel: UniverseMembershipSQLModel from repository

    Returns:
        UniverseMembership dataclass for service/command layers
    """
    from models.dataclass.universe import UniverseMembership

    return UniverseMembership(
        id=sqlmodel.id,
        universe_id=sqlmodel.universe_id,
        asset_id=sqlmodel.asset_id,
        added_date=sqlmodel.added_date,
        removed_date=sqlmodel.removed_date,
        reason=sqlmodel.reason,
        is_active=sqlmodel.is_active
    )


def convert_sentiment_event_sqlmodel_to_dataclass(sqlmodel: "SentimentEventSQLModel") -> "SentimentEvent":
    """Convert SentimentEventSQLModel to SentimentEvent dataclass.

    Args:
        sqlmodel: SentimentEventSQLModel from repository

    Returns:
        SentimentEvent dataclass for service/command layers
    """
    from models.dataclass.sentiment_event import SentimentEvent
    from decimal import Decimal
    import json

    # Parse details JSON
    details = json.loads(sqlmodel.details) if sqlmodel.details else {}

    return SentimentEvent(
        id=sqlmodel.id,
        asset_id=sqlmodel.asset_id,
        sentiment_type_id=sqlmodel.sentiment_type_id,
        event_date=sqlmodel.event_date,
        event_time=sqlmodel.event_time,
        session=sqlmodel.session,
        value=Decimal(str(sqlmodel.value)) if sqlmodel.value else Decimal("0"),
        magnitude=sqlmodel.magnitude or "small",
        details=details,
        created_at=sqlmodel.created_at
    )


def convert_fed_data_sqlmodel_to_dataclass(sqlmodel: "FedDataSQLModel") -> "FedData":
    """Convert FedDataSQLModel to FedData dataclass.

    Args:
        sqlmodel: FedDataSQLModel from repository

    Returns:
        FedData dataclass for service/command layers
    """
    from models.dataclass.fed_data import FedData
    from decimal import Decimal
    import json

    return FedData(
        id=sqlmodel.id,
        data_type=sqlmodel.data_type,
        observation_date=sqlmodel.observation_date,
        value=Decimal(str(sqlmodel.value)),
        details=json.loads(sqlmodel.details) if sqlmodel.details else {},
        created_at=sqlmodel.created_at,
        updated_at=sqlmodel.updated_at
    )
