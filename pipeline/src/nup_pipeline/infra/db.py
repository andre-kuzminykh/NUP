"""SQLAlchemy ORM Base + engine factory.

create_all() is invoked from each repo's __init__ — это OK для текущего MVP
(нет миграционных конфликтов; таблицы простые). При появлении Alembic
переключим на `alembic upgrade head` в стартовом hook'е.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(database_url, future=True, echo=echo, pool_pre_ping=True)
