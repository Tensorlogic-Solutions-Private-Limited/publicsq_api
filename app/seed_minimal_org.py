"""
Minimal Organizational Structure Seeding Script

This script creates a minimal organizational hierarchy for testing purposes.
It creates one organization, one block, and one school with basic admin users.

Usage:
    python -m app.seed_minimal_org
"""

import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal, Base, engine
from app.models.user import Role, User
from app.models.organization import Organization, Block, School
from app.utils.auth import get_password_hash
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_minimal_org():
    """Create minimal organizational structure for testing."""
    logger.info("Creating minimal organizational structure...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Ensure database tables exist
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Create organization
            org_result = await session.execute(
                select(Organization).where(Organization.org_code == "TEST_ORG")
            )
            organization = org_result.scalar_one_or_none()
            
            if not organization:
                organization = Organization(
                    org_code="TEST_ORG",
                    org_name="Test Organization",
                    org_description="Test organization for development",
                    is_active=True
                )
                session.add(organization)
                await session.flush()
                logger.info("Created test organization")
            
            # Create block
            block_result = await session.execute(
                select(Block).where(Block.block_code == "TEST_BLOCK")
            )
            block = block_result.scalar_one_or_none()
            
            if not block:
                block = Block(
                    block_code="TEST_BLOCK",
                    block_name="Test Block",
                    block_description="Test block for development",
                    organization_id=organization.id,
                    is_active=True
                )
                session.add(block)
                await session.flush()
                logger.info("Created test block")
            
            # Create school
            school_result = await session.execute(
                select(School).where(School.udise_code == "TEST_SCHOOL")
            )
            school = school_result.scalar_one_or_none()
            
            if not school:
                school = School(
                    udise_code="TEST_SCHOOL",
                    school_name="Test School",
                    school_description="Test school for development",
                    block_id=block.id,
                    organization_id=organization.id,
                    is_active=True
                )
                session.add(school)
                await session.flush()
                logger.info("Created test school")
            
            # Create basic admin user if roles exist
            admin_role_result = await session.execute(
                select(Role).where(Role.role_code == "super_admin")
            )
            admin_role = admin_role_result.scalar_one_or_none()
            
            if admin_role:
                admin_result = await session.execute(
                    select(User).where(User.username == "testadmin")
                )
                admin_user = admin_result.scalar_one_or_none()
                
                if not admin_user:
                    admin_user = User(
                        username="testadmin",
                        hashed_password=get_password_hash("testadmin123"),
                        full_name="Test Administrator",
                        email="testadmin@test.org",
                        role_id=admin_role.id,
                        organization_id=organization.id,
                        is_active=True
                    )
                    session.add(admin_user)
                    logger.info("Created test admin user")
            
            await session.commit()
            logger.info("Minimal organizational structure created successfully!")
            
        except Exception as e:
            logger.error(f"Error creating minimal org structure: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_minimal_org())