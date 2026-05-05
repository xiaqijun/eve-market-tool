"""Initial schema — all core tables for EVE Market Tool.

Revision ID: 001
Revises: None
Create Date: 2026-05-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- region ---
    op.create_table(
        "region",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("eve_region_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("station_id", sa.BigInteger(), nullable=True),
        sa.Column("solar_system_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eve_region_id"),
    )

    # --- item ---
    op.create_table(
        "item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("base_price", sa.Float(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("icon_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id"),
    )
    op.create_index("ix_item_name", "item", ["name"])
    op.create_index("ix_item_group_id", "item", ["group_id"])
    op.create_index("ix_item_type_id", "item", ["type_id"])

    # --- market_group ---
    op.create_table(
        "market_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("eve_group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_group_id", sa.Integer(), nullable=True),
        sa.Column("has_types", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eve_group_id"),
    )

    # --- market_order_snapshot ---
    op.create_table(
        "market_order_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=True),
        sa.Column("is_buy_order", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("volume_remain", sa.Integer(), nullable=False),
        sa.Column("volume_total", sa.Integer(), nullable=False),
        sa.Column("min_volume", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("range", sa.String(50), nullable=False, server_default=sa.text("'station'")),
        sa.Column("issued", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "fetched_at", name="uq_order_fetch"),
    )
    op.create_index("ix_mos_type_region", "market_order_snapshot", ["type_id", "region_id", "fetched_at"])
    op.create_index("ix_mos_fetched", "market_order_snapshot", ["fetched_at"])
    op.create_index("ix_mos_type_region_buy", "market_order_snapshot", ["type_id", "region_id", "is_buy_order", "fetched_at"])

    # --- market_history_daily ---
    op.create_table(
        "market_history_daily",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("average", sa.Float(), nullable=True),
        sa.Column("highest", sa.Float(), nullable=True),
        sa.Column("lowest", sa.Float(), nullable=True),
        sa.Column("order_count", sa.BigInteger(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id", "region_id", "date", name="uq_history_type_region_date"),
    )
    op.create_index("ix_mhd_type_region_date", "market_history_daily", ["type_id", "region_id", "date"])

    # --- market_price ---
    op.create_table(
        "market_price",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("adjusted_price", sa.Float(), nullable=True),
        sa.Column("average_price", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id"),
    )

    # --- user ---
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("character_id", sa.BigInteger(), nullable=False),
        sa.Column("character_name", sa.String(200), nullable=False),
        sa.Column("corporation_id", sa.Integer(), nullable=True),
        sa.Column("alliance_id", sa.Integer(), nullable=True),
        sa.Column("access_token_hash", sa.String(255), nullable=True),
        sa.Column("refresh_token_hash", sa.String(255), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id"),
    )

    # --- station_trade ---
    op.create_table(
        "station_trade",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.BigInteger(), nullable=False),
        sa.Column("buy_order_id", sa.BigInteger(), nullable=True),
        sa.Column("sell_order_id", sa.BigInteger(), nullable=True),
        sa.Column("buy_price", sa.Float(), nullable=False),
        sa.Column("sell_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("volume_remaining", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'scouting'")),
        sa.Column("net_profit", sa.Float(), nullable=True),
        sa.Column("profit_margin", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_st_user_status", "station_trade", ["user_id", "status"])
    op.create_index("ix_st_type_region", "station_trade", ["type_id", "region_id"])

    # --- arbitrage_opportunity ---
    op.create_table(
        "arbitrage_opportunity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("buy_region_id", sa.Integer(), nullable=False),
        sa.Column("sell_region_id", sa.Integer(), nullable=False),
        sa.Column("buy_price", sa.Float(), nullable=False),
        sa.Column("sell_price", sa.Float(), nullable=False),
        sa.Column("buy_volume", sa.Integer(), nullable=False),
        sa.Column("sell_volume", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("profit_per_unit", sa.Float(), nullable=False),
        sa.Column("profit_margin", sa.Float(), nullable=False),
        sa.Column("total_profit", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id", "buy_region_id", "sell_region_id", "detected_at", name="uq_arb_opportunity"),
    )
    op.create_index("ix_ao_detected", "arbitrage_opportunity", ["detected_at"])
    op.create_index("ix_ao_type", "arbitrage_opportunity", ["type_id"])
    op.create_index("ix_ao_profit", "arbitrage_opportunity", ["total_profit"])

    # --- blueprint ---
    op.create_table(
        "blueprint",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("blueprint_type_id", sa.Integer(), nullable=False),
        sa.Column("product_type_id", sa.Integer(), nullable=False),
        sa.Column("manufacturing_time", sa.Integer(), nullable=False),
        sa.Column("max_production_limit", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("activity_type", sa.String(20), nullable=False, server_default=sa.text("'manufacturing'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blueprint_type_id"),
    )
    op.create_index("ix_bp_product", "blueprint", ["product_type_id"])

    # --- blueprint_material ---
    op.create_table(
        "blueprint_material",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("blueprint.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bm_blueprint", "blueprint_material", ["blueprint_id"])

    # --- manufacturing_analysis ---
    op.create_table(
        "manufacturing_analysis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("product_type_id", sa.Integer(), nullable=False),
        sa.Column("blueprint_type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("materials_cost", sa.Float(), nullable=False),
        sa.Column("job_installation_fee", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_production_cost", sa.Float(), nullable=False),
        sa.Column("market_sell_price", sa.Float(), nullable=False),
        sa.Column("market_buy_price", sa.Float(), nullable=False),
        sa.Column("estimated_profit", sa.Float(), nullable=False),
        sa.Column("profit_margin", sa.Float(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ma_product", "manufacturing_analysis", ["product_type_id", "region_id"])
    op.create_index("ix_ma_user", "manufacturing_analysis", ["user_id"])

    # --- price_alert ---
    op.create_table(
        "price_alert",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("condition", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("last_triggered", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pa_user_active", "price_alert", ["user_id", "is_active"])

    # --- hot_item ---
    op.create_table(
        "hot_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("volume_change_pct", sa.Float(), nullable=True),
        sa.Column("price_change_pct", sa.Float(), nullable=True),
        sa.Column("spike_score", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hi_detected", "hot_item", ["detected_at"])
    op.create_index("ix_hi_score", "hot_item", ["spike_score"])


def downgrade() -> None:
    op.drop_index("ix_hi_score", table_name="hot_item")
    op.drop_index("ix_hi_detected", table_name="hot_item")
    op.drop_table("hot_item")

    op.drop_index("ix_pa_user_active", table_name="price_alert")
    op.drop_table("price_alert")

    op.drop_index("ix_ma_user", table_name="manufacturing_analysis")
    op.drop_index("ix_ma_product", table_name="manufacturing_analysis")
    op.drop_table("manufacturing_analysis")

    op.drop_index("ix_bm_blueprint", table_name="blueprint_material")
    op.drop_table("blueprint_material")

    op.drop_index("ix_bp_product", table_name="blueprint")
    op.drop_table("blueprint")

    op.drop_index("ix_ao_profit", table_name="arbitrage_opportunity")
    op.drop_index("ix_ao_type", table_name="arbitrage_opportunity")
    op.drop_index("ix_ao_detected", table_name="arbitrage_opportunity")
    op.drop_table("arbitrage_opportunity")

    op.drop_index("ix_st_type_region", table_name="station_trade")
    op.drop_index("ix_st_user_status", table_name="station_trade")
    op.drop_table("station_trade")

    op.drop_table("user")

    op.drop_table("market_price")

    op.drop_index("ix_mhd_type_region_date", table_name="market_history_daily")
    op.drop_table("market_history_daily")

    op.drop_index("ix_mos_type_region_buy", table_name="market_order_snapshot")
    op.drop_index("ix_mos_fetched", table_name="market_order_snapshot")
    op.drop_index("ix_mos_type_region", table_name="market_order_snapshot")
    op.drop_table("market_order_snapshot")

    op.drop_table("market_group")

    op.drop_index("ix_item_type_id", table_name="item")
    op.drop_index("ix_item_group_id", table_name="item")
    op.drop_index("ix_item_name", table_name="item")
    op.drop_table("item")

    op.drop_table("region")
