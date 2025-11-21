import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal, Base, engine
from app.models.user import Role, User
from app.models.organization import Organization
from app.models.master import *
from app.utils.auth import get_password_hash

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Insert Roles if missing - using correct generic role structure
        result = await session.execute(select(Role))
        if not result.scalar():
            session.add_all([
                Role(role_name="Super Admin", role_code="super_admin"),
                Role(role_name="Admin", role_code="admin"),
                Role(role_name="Admin-User", role_code="admin_user"),
                Role(role_name="Block Admin", role_code="block_admin"),
                Role(role_name="Teacher", role_code="teacher")
                # Note: School Admin role is ignored for MVP
            ])
            await session.commit()

        # Insert Question_Type
        result = await session.execute(select(Question_Type))
        if not result.scalar():
            session.add_all([
                Question_Type(qtm_type_code="1000", qtm_type_name="MCQ")
            ])
            await session.commit()

        # Insert Medium and get ID
        result = await session.execute(select(Medium))
        english_medium = result.scalar()
        if not english_medium:
            english_medium = Medium(mmt_medium_code="2000", mmt_medium_name="English")
            session.add(english_medium)
            await session.commit()
            await session.refresh(english_medium)

        # Insert Subject using the actual medium ID
        result = await session.execute(select(Subject))
        if not result.scalar():
            session.add_all([
                Subject(
                    smt_subject_code="3000",
                    smt_subject_name="Social Science",
                    smt_standard="10",
                    smt_medium_id=english_medium.id
                )
            ])
            await session.commit()

        # Insert Criteria
        result = await session.execute(select(Criteria))
        if not result.scalar():
            session.add_all([
                Criteria(scm_criteria_code="4000", scm_criteria_name="Chapter"),
                Criteria(scm_criteria_code="4001", scm_criteria_name="Topic")
            ])
            await session.commit()

        # Insert Question_Format
        result = await session.execute(select(Question_Format))
        if not result.scalar():
            session.add_all([
                Question_Format(qfm_format_code="5000", qfm_format_name="Text")
            ])
            await session.commit()

        # Insert CognitiveLearning
        result = await session.execute(select(CognitiveLearning))
        if not result.scalar():
            session.add_all([
                CognitiveLearning(cognitive_learning_name="Understanding"),
                CognitiveLearning(cognitive_learning_name="Knowledge"),
                CognitiveLearning(cognitive_learning_name="Application"),
                CognitiveLearning(cognitive_learning_name="Analysis"),
                CognitiveLearning(cognitive_learning_name="Evaluation"),
                CognitiveLearning(cognitive_learning_name="Synthesis")
            ])
            await session.commit()

        # Insert Difficulty
        result = await session.execute(select(Difficulty))
        if not result.scalar():
            session.add_all([
                Difficulty(difficulty_name="Easy"),
                Difficulty(difficulty_name="Medium"),
                Difficulty(difficulty_name="Hard")
            ])
            await session.commit()

        # 🔐 Create 'superadmin' user with super admin role if not exists
        result = await session.execute(select(User).where(User.username == "superadmin"))
        existing_user = result.scalar_one_or_none()
        if not existing_user:
            # Check if super_admin role exists, create if not
            role_result = await session.execute(select(Role).where(Role.role_code == "super_admin"))
            super_admin_role = role_result.scalar_one_or_none()
            
            if not super_admin_role:
                super_admin_role = Role(role_name="Super Admin", role_code="super_admin")
                session.add(super_admin_role)
                await session.commit()
                await session.refresh(super_admin_role)

            # Create default organization for super admin if needed
            from app.models.organization import Organization
            org_result = await session.execute(select(Organization).where(Organization.org_code == "VIDYASHAKTHI"))
            default_org = org_result.scalar_one_or_none()
            
            if not default_org:
                default_org = Organization(
                    org_code="VIDYASHAKTHI",
                    org_name="VidyaShakthi",
                    org_description="Default organization",
                    is_active=True
                )
                session.add(default_org)
                await session.commit()
                await session.refresh(default_org)

            new_user = User(
                username="superadmin",
                hashed_password=get_password_hash("superadmin"),
                full_name="Super Administrator",
                email="superadmin@vidyashakthi.com",
                role_id=super_admin_role.id,
                organization_id=default_org.id,
                is_active=True
            )
            session.add(new_user)
            await session.commit()
            print("superadmin user created with super admin role and organizational context.")

if __name__ == "__main__":
    asyncio.run(init_db())