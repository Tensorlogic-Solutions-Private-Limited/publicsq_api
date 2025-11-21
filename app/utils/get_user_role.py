from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.user import Role


async def get_user_role(db: AsyncSession, role_id: int):
    role_obj = await db.scalar(select(Role).where(Role.id == role_id))
    if not role_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found.")
    return role_obj