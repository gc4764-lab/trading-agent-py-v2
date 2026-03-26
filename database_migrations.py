# database_migrations.py - Alembic Database Migrations
"""
Database migration management using Alembic
Run: alembic revision --autogenerate -m "description"
     alembic upgrade head
"""

# alembic/env.py
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# alembic/versions/001_initial_schema.py
"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Create orders table
    op.create_table(
        'orders',
        sa.Column('order_id', sa.String(50), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(4), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('price', sa.Float),
        sa.Column('stop_price', sa.Float),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.Index('idx_orders_symbol', 'symbol'),
        sa.Index('idx_orders_status', 'status'),
        sa.Index('idx_orders_created', 'created_at')
    )
    
    # Create positions table
    op.create_table(
        'positions',
        sa.Column('symbol', sa.String(20), primary_key=True),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('avg_price', sa.Float, nullable=False),
        sa.Column('current_price', sa.Float),
        sa.Column('unrealized_pnl', sa.Float),
        sa.Column('realized_pnl', sa.Float, default=0),
        sa.Column('updated_at', sa.DateTime, nullable=False)
    )
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('alert_id', sa.String(20), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('condition_type', sa.String(50), nullable=False),
        sa.Column('condition_value', sa.Float, nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('order_details', sa.Text),
        sa.Column('webhook_url', sa.String(500)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('triggered_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Index('idx_alerts_symbol', 'symbol'),
        sa.Index('idx_alerts_active', 'is_active')
    )
    
    # Create risk_metrics table
    op.create_table(
        'risk_metrics',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('date', sa.DateTime, nullable=False),
        sa.Column('daily_pnl', sa.Float),
        sa.Column('total_exposure', sa.Float),
        sa.Column('drawdown', sa.Float),
        sa.Column('winning_trades', sa.Integer),
        sa.Column('losing_trades', sa.Integer),
        sa.Column('var_95', sa.Float),
        sa.Column('sharpe_ratio', sa.Float),
        sa.Index('idx_risk_date', 'date')
    )
    
    # Create strategy_signals table
    op.create_table(
        'strategy_signals',
        sa.Column('signal_id', sa.String(50), primary_key=True),
        sa.Column('strategy_id', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(4), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('price', sa.Float),
        sa.Column('status', sa.String(20)),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Index('idx_signals_strategy', 'strategy_id'),
        sa.Index('idx_signals_symbol', 'symbol')
    )

def downgrade() -> None:
    op.drop_table('strategy_signals')
    op.drop_table('risk_metrics')
    op.drop_table('alerts')
    op.drop_table('positions')
    op.drop_table('orders')
    