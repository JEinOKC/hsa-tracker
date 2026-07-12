"""Alembic migration environment"""

from logging.config import fileConfig

from alembic import context
from app.config import settings

# Import the Base and all models
from app.database import Base

# Import all models so Alembic can detect them
from app.models import User, UserBackupCode, UserPasskey, UserTOTP  # noqa: F401
from app.models.access import AccountAccess, AccountRole  # noqa: F401
from app.models.bank import (  # noqa: F401
    BankConnection,
    BankTransaction,
    TransactionDocument,
)
from app.models.family import FamilyMember, HsaEligibilityPeriod  # noqa: F401
from app.models.household import (  # noqa: F401
    Household,
    HouseholdMembership,
    HouseholdRole,
)
from app.models.lmn import LmnDocument  # noqa: F401
from app.models.push_subscription import PushSubscription  # noqa: F401
from app.models.user import FamilyInvite, RegistrationToken  # noqa: F401
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from settings.
# Strip pgbouncer=true if present — PgBouncer pooling is incompatible with migrations.
_db_url = settings.database_url
for _param in ("?pgbouncer=true", "&pgbouncer=true"):
    _db_url = _db_url.replace(_param, "")
config.set_main_option("sqlalchemy.url", _db_url)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
