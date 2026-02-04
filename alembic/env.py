"""Alembic environment configuration for database migrations."""

from logging.config import fileConfig

from sqlalchemy import create_engine
from alembic import context

# Import Base directly to avoid importing session which creates engine
from app.db.base import Base

# Import all models to ensure they are registered with Base.metadata
# This must be done before target_metadata is set
# Import models after Base to avoid circular imports
import app.users.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.ai.models  # noqa: F401
import app.attendances.models  # noqa: F401
import app.clients.models  # noqa: F401
import app.properties.models  # noqa: F401
import app.visits.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from application settings
# Import settings only when needed to avoid creating engine with invalid URL
from app.config.settings import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
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
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Create engine from settings to avoid importing app.db.session
    # which would create engine with potentially invalid URL at import time
    connectable = create_engine(
        settings.database_url,
        pool_pre_ping=True,
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

