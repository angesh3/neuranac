import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from sqlalchemy import MetaData
from app.config import get_settings
from app.models.admin import Base as AdminBase
from app.models.network import Base as NetworkBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Merge metadata from all ORM bases so autogenerate sees every table
def _combine_metadata(*bases) -> MetaData:
    m = MetaData()
    for base in bases:
        for table in base.metadata.tables.values():
            table.tometadata(m)
    return m

target_metadata = _combine_metadata(AdminBase, NetworkBase)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
