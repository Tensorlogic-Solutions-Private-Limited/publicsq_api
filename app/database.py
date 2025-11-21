import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file
load_dotenv()

# Define the database URL (it will use the environment variable)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://admin:admin@localhost/smartqp_fastapi_v5")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a sessionmaker bound to the engine
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Create the base class for declarative models
Base = declarative_base()

# Dependency to get the database session
async def get_db():
    async with AsyncSessionLocal() as db:  # Use async with to manage the session context
        try:
            yield db
        finally:
            # No need for `await db.close()` here, `async with` handles it
            pass
