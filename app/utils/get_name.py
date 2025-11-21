from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select

async def get_name(db, table, id_field, id_value, name_field):
    stmt = select(table).where(id_field == id_value)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    return getattr(obj, name_field, "Unknown") if obj else "Unknown"