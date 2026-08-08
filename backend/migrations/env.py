from logging.config import fileConfig
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool


# --------------------------------------------------
# 加载项目路径
# --------------------------------------------------

# backend 目录加入 Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))


# --------------------------------------------------
# 加载 .env
# --------------------------------------------------

# env.py 位于:
# backend/migrations/env.py
#
# .env 位于:
# backend/.env

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)


# --------------------------------------------------
# 导入数据库 Base 和模型
# --------------------------------------------------

from app.database.base import Base, import_models  # noqa: E402


# --------------------------------------------------
# Alembic 配置
# --------------------------------------------------

config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# --------------------------------------------------
# 使用 .env 中的 DATABASE_URL
# --------------------------------------------------

database_url = os.getenv("DATABASE_URL")

if database_url:
    config.set_main_option(
        "sqlalchemy.url",
        database_url
    )
else:
    raise RuntimeError(
        "DATABASE_URL 未配置，请检查 backend/.env"
    )


# --------------------------------------------------
# 加载所有模型
# --------------------------------------------------

import_models()


# Alembic 自动检测模型变化
target_metadata = Base.metadata



# --------------------------------------------------
# Offline migration
# --------------------------------------------------

def run_migrations_offline() -> None:
    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()



# --------------------------------------------------
# Online migration
# --------------------------------------------------

def run_migrations_online() -> None:

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )


    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )


        with context.begin_transaction():
            context.run_migrations()



# --------------------------------------------------
# Main
# --------------------------------------------------

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()