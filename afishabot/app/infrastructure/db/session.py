from curses import echo
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings


engine = create_async_engine(
    settings.database.build_dsn(),
    echo=False 
)

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

