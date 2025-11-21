"""
RBAC Data Seeding Script

This script creates the initial organizational hierarchy, permissions, role-permission mappings,
and admin users for the hierarchical RBAC system.

Usage:
    python -m app.init_rbac_data
"""

import asyncio
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.database import AsyncSessionLocal, Base, engine
from app.models.user import Role, User
from app.models.organization import Organization, Block, School
from app.models.permission import Permission, RolePermission
from app.utils.auth import get_password_hash
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RBACDataSeeder:
    """Main class for seeding RBAC data."""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def seed_all(self):
        """Seed all RBAC data in the correct order."""
        logger.info("Starting RBAC data seeding...")
        
        try:
            # Create database tables if they don't exist
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Seed in dependency order
            await self.seed_roles()
            await self.seed_organizational_hierarchy()
            await self.seed_permissions()
            await self.seed_role_permissions()
            await self.seed_admin_users()
            
            logger.info("RBAC data seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during seeding: {e}")
            await self.session.rollback()
            raise
    
    async def seed_roles(self):
        """Create the six main roles for the RBAC system."""
        logger.info("Seeding roles...")
        
        roles_data = [
            {"role_code": "super_admin", "role_name": "Super Admin"},
            {"role_code": "admin", "role_name": "Admin"},
            {"role_code": "admin_user", "role_name": "Admin-User"},
            {"role_code": "block_admin", "role_name": "Block Admin"},
            {"role_code": "teacher", "role_name": "Teacher"}
        ]
        
        for role_data in roles_data:
            # Check if role already exists
            result = await self.session.execute(
                select(Role).where(Role.role_code == role_data["role_code"])
            )
            existing_role = result.scalar_one_or_none()
            
            if not existing_role:
                role = Role(**role_data)
                self.session.add(role)
                logger.info(f"Created role: {role_data['role_name']}")
            else:
                logger.info(f"Role already exists: {role_data['role_name']}")
        
        await self.session.commit()
    
    async def seed_organizational_hierarchy(self):
        """Create default organizational hierarchy structure."""
        logger.info("Seeding organizational hierarchy...")
        
        # Create default organization
        org_result = await self.session.execute(
            select(Organization).where(Organization.org_code == "VIDYASHAKTHI")
        )
        organization = org_result.scalar_one_or_none()
        
        if not organization:
            organization = Organization(
                org_code="VIDYASHAKTHI",
                org_name="VidyaShakthi Education",
                org_description="Main educational organization",
                is_active=True
            )
            self.session.add(organization)
            await self.session.flush()  # Get the ID
            logger.info("Created default organization: VidyaShakthi Education")
        else:
            logger.info("Organization already exists: VidyaShakthi Education")
        
        # Create default blocks
        blocks_data = [
            {
                "block_code": "BLOCK_NORTH",
                "block_name": "North Block",
                "block_description": "Northern region block",
                "organization_id": organization.id
            },
            {
                "block_code": "BLOCK_SOUTH",
                "block_name": "South Block", 
                "block_description": "Southern region block",
                "organization_id": organization.id
            }
        ]
        
        created_blocks = []
        for block_data in blocks_data:
            block_result = await self.session.execute(
                select(Block).where(Block.block_code == block_data["block_code"])
            )
            block = block_result.scalar_one_or_none()
            
            if not block:
                block = Block(**block_data)
                self.session.add(block)
                await self.session.flush()  # Get the ID
                logger.info(f"Created block: {block_data['block_name']}")
            else:
                logger.info(f"Block already exists: {block_data['block_name']}")
            
            created_blocks.append(block)
        
        # Create default schools
        schools_data = [
            {
                "udise_code": "SCHOOL_NORTH_01",
                "school_name": "North Primary School",
                "school_description": "Primary school in north block",
                "block_id": created_blocks[0].id,
                "organization_id": organization.id
            },
            {
                "udise_code": "SCHOOL_NORTH_02", 
                "school_name": "North Secondary School",
                "school_description": "Secondary school in north block",
                "block_id": created_blocks[0].id,
                "organization_id": organization.id
            },
            {
                "udise_code": "SCHOOL_SOUTH_01",
                "school_name": "South Primary School", 
                "school_description": "Primary school in south block",
                "block_id": created_blocks[1].id,
                "organization_id": organization.id
            }
        ]
        
        for school_data in schools_data:
            school_result = await self.session.execute(
                select(School).where(School.udise_code == school_data["udise_code"])
            )
            school = school_result.scalar_one_or_none()
            
            if not school:
                school = School(**school_data)
                self.session.add(school)
                logger.info(f"Created school: {school_data['school_name']}")
            else:
                logger.info(f"School already exists: {school_data['school_name']}")
        
        await self.session.commit()
    
    async def seed_permissions(self):
        """Create all permissions based on the role matrix."""
        logger.info("Seeding permissions...")
        
        permissions_data = [
            # Question Bank Permissions
            {
                "permission_code": "question_bank.upload",
                "permission_name": "Upload Question Bank",
                "permission_description": "Permission to upload questions to the question bank",
                "resource_type": "question_bank",
                "action_type": "create"
            },
            {
                "permission_code": "question_bank.view",
                "permission_name": "View Question Bank",
                "permission_description": "Permission to view questions in the question bank",
                "resource_type": "question_bank", 
                "action_type": "read"
            },
            {
                "permission_code": "question_bank.edit",
                "permission_name": "Edit Question in Question Bank",
                "permission_description": "Permission to edit questions in the question bank",
                "resource_type": "question_bank",
                "action_type": "update"
            },
            {
                "permission_code": "question_bank.delete",
                "permission_name": "Delete Question in Question Bank",
                "permission_description": "Permission to delete questions from the question bank",
                "resource_type": "question_bank",
                "action_type": "delete"
            },
            
            # Quiz Permissions
            {
                "permission_code": "quiz.create",
                "permission_name": "Create Quiz",
                "permission_description": "Permission to create new quizzes",
                "resource_type": "quiz",
                "action_type": "create"
            },
            {
                "permission_code": "quiz.view",
                "permission_name": "View Quiz",
                "permission_description": "Permission to view quizzes",
                "resource_type": "quiz",
                "action_type": "read"
            },
            {
                "permission_code": "quiz.edit_properties",
                "permission_name": "Edit Quiz Properties",
                "permission_description": "Permission to edit quiz properties",
                "resource_type": "quiz",
                "action_type": "update"
            },
            {
                "permission_code": "quiz.edit_questions",
                "permission_name": "Edit Questions in Quiz",
                "permission_description": "Permission to edit questions within a quiz",
                "resource_type": "quiz",
                "action_type": "update"
            },
            {
                "permission_code": "quiz.delete",
                "permission_name": "Delete Quiz",
                "permission_description": "Permission to delete quizzes",
                "resource_type": "quiz",
                "action_type": "delete"
            },
            {
                "permission_code": "quiz.delete_questions",
                "permission_name": "Delete Questions in Quiz",
                "permission_description": "Permission to delete questions from a quiz",
                "resource_type": "quiz",
                "action_type": "delete"
            },
            {
                "permission_code": "quiz.conduct",
                "permission_name": "Conduct Quiz",
                "permission_description": "Permission to conduct/administer quizzes",
                "resource_type": "quiz",
                "action_type": "execute"
            },
            
            # User Management Permissions
            {
                "permission_code": "user.create",
                "permission_name": "Create User",
                "permission_description": "Permission to create new users",
                "resource_type": "user",
                "action_type": "create"
            },
            {
                "permission_code": "user.list",
                "permission_name": "List Users",
                "permission_description": "Permission to list users",
                "resource_type": "user",
                "action_type": "read"
            },
            {
                "permission_code": "user.view",
                "permission_name": "View User Details",
                "permission_description": "Permission to view user details",
                "resource_type": "user",
                "action_type": "read"
            },
            {
                "permission_code": "user.edit",
                "permission_name": "Edit User",
                "permission_description": "Permission to edit user information",
                "resource_type": "user",
                "action_type": "update"
            },
            {
                "permission_code": "user.delete",
                "permission_name": "Delete User",
                "permission_description": "Permission to delete users",
                "resource_type": "user",
                "action_type": "delete"
            },
            
            # School Management Permissions
            {
                "permission_code": "school.create",
                "permission_name": "Create School",
                "permission_description": "Permission to create new schools",
                "resource_type": "school",
                "action_type": "create"
            },
            {
                "permission_code": "school.list",
                "permission_name": "List Schools",
                "permission_description": "Permission to list schools",
                "resource_type": "school",
                "action_type": "read"
            },
            {
                "permission_code": "school.view",
                "permission_name": "View School Details",
                "permission_description": "Permission to view school details",
                "resource_type": "school",
                "action_type": "read"
            },
            {
                "permission_code": "school.edit",
                "permission_name": "Edit School",
                "permission_description": "Permission to edit school information",
                "resource_type": "school",
                "action_type": "update"
            },
            {
                "permission_code": "school.delete",
                "permission_name": "Delete School",
                "permission_description": "Permission to delete schools",
                "resource_type": "school",
                "action_type": "delete"
            },
            
            # Teacher Management Permissions (separate from general user management)
            {
                "permission_code": "teacher.create",
                "permission_name": "Create Teacher",
                "permission_description": "Permission to create teacher accounts",
                "resource_type": "teacher",
                "action_type": "create"
            },
            {
                "permission_code": "teacher.list",
                "permission_name": "List Teachers",
                "permission_description": "Permission to list teachers",
                "resource_type": "teacher",
                "action_type": "read"
            },
            {
                "permission_code": "teacher.view",
                "permission_name": "View Teacher Details",
                "permission_description": "Permission to view teacher details",
                "resource_type": "teacher",
                "action_type": "read"
            },
            {
                "permission_code": "teacher.edit",
                "permission_name": "Edit Teacher",
                "permission_description": "Permission to edit teacher information",
                "resource_type": "teacher",
                "action_type": "update"
            },
            {
                "permission_code": "teacher.delete",
                "permission_name": "Delete Teacher",
                "permission_description": "Permission to delete teacher accounts",
                "resource_type": "teacher",
                "action_type": "delete"
            }
        ]
        
        for perm_data in permissions_data:
            # Check if permission already exists
            result = await self.session.execute(
                select(Permission).where(Permission.permission_code == perm_data["permission_code"])
            )
            existing_permission = result.scalar_one_or_none()
            
            if not existing_permission:
                permission = Permission(**perm_data)
                self.session.add(permission)
                logger.info(f"Created permission: {perm_data['permission_name']}")
            else:
                logger.info(f"Permission already exists: {perm_data['permission_name']}")
        
        await self.session.commit()
    
    async def seed_role_permissions(self):
        """Create role-permission mappings based on the CSV matrix."""
        logger.info("Seeding role-permission mappings...")
        
        # Get all roles and permissions
        roles_result = await self.session.execute(select(Role))
        roles = {role.role_code: role for role in roles_result.scalars().all()}
        
        permissions_result = await self.session.execute(select(Permission))
        permissions = {perm.permission_code: perm for perm in permissions_result.scalars().all()}
        
        # Define role-permission mappings based on the CSV matrix
        role_permission_mappings = {
            "super_admin": [
                # Question Bank - Full access
                ("question_bank.upload", False),
                ("question_bank.view", False),
                ("question_bank.edit", False),
                ("question_bank.delete", False),
                # Quiz - Admin level access (delete only)
                ("quiz.delete", False),
                # User Management - Full access
                ("user.create", False),
                ("user.list", False),
                ("user.view", False),
                ("user.edit", False),
                ("user.delete", False),
                # School Management - Full access
                ("school.create", False),
                ("school.list", False),
                ("school.view", False),
                ("school.edit", False),
                ("school.delete", False),
                # Teacher Management - Full access
                ("teacher.create", False),
                ("teacher.list", False),
                ("teacher.view", False),
                ("teacher.edit", False),
                ("teacher.delete", False)
            ],
            
            "admin": [
                # Question Bank - Full access
                ("question_bank.upload", False),
                ("question_bank.view", False),
                ("question_bank.edit", False),
                ("question_bank.delete", False),
                # Quiz - Admin level access (delete only)
                ("quiz.delete", False),
                # User Management - Full access
                ("user.create", False),
                ("user.list", False),
                ("user.view", False),
                ("user.edit", False),
                ("user.delete", False),
                # School Management - Full access
                ("school.create", False),
                ("school.list", False),
                ("school.view", False),
                ("school.edit", False),
                ("school.delete", False),
                # Teacher Management - Full access
                ("teacher.create", False),
                ("teacher.list", False),
                ("teacher.view", False),
                ("teacher.edit", False),
                ("teacher.delete", False)
            ],
            
            "admin_user": [
                # Question Bank - Full access
                ("question_bank.upload", False),
                ("question_bank.view", False),
                ("question_bank.edit", False),
                ("question_bank.delete", False),
                # Quiz - Admin level access (delete only)
                ("quiz.delete", False),
                # User Management - Full access
                ("user.create", False),
                ("user.list", False),
                ("user.view", False),
                ("user.edit", False),
                ("user.delete", False),
                # School Management - Full access
                ("school.create", False),
                ("school.list", False),
                ("school.view", False),
                ("school.edit", False),
                ("school.delete", False),
                # Teacher Management - Full access
                ("teacher.create", False),
                ("teacher.list", False),
                ("teacher.view", False),
                ("teacher.edit", False),
                ("teacher.delete", False)
            ],
            
            "block_admin": [
                # Question Bank - Full access
                ("question_bank.upload", False),
                ("question_bank.view", False),
                ("question_bank.edit", False),
                ("question_bank.delete", False),
                # Quiz - Admin level access (delete only)
                ("quiz.delete", False),
                # User Management - Full access
                ("user.create", False),
                ("user.list", False),
                ("user.view", False),
                ("user.edit", False),
                ("user.delete", False),
                # School Management - Full access
                ("school.create", False),
                ("school.list", False),
                ("school.view", False),
                ("school.edit", False),
                ("school.delete", False),
                # Teacher Management - Full access
                ("teacher.create", False),
                ("teacher.list", False),
                ("teacher.view", False),
                ("teacher.edit", False),
                ("teacher.delete", False)
            ],
            
            "teacher": [
                # Quiz - Full teacher access
                ("quiz.create", False),
                ("quiz.view", False),
                ("quiz.edit_properties", False),
                ("quiz.edit_questions", False),
                ("quiz.delete_questions", False),
                ("quiz.conduct", False)
            ]
        }
        
        # Create role-permission mappings
        for role_code, permission_mappings in role_permission_mappings.items():
            role = roles.get(role_code)
            if not role:
                logger.warning(f"Role not found: {role_code}")
                continue
            
            for permission_code, has_ownership_restriction in permission_mappings:
                permission = permissions.get(permission_code)
                if not permission:
                    logger.warning(f"Permission not found: {permission_code}")
                    continue
                
                # Check if mapping already exists
                result = await self.session.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == permission.id
                    )
                )
                existing_mapping = result.scalar_one_or_none()
                
                if not existing_mapping:
                    role_permission = RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                        has_ownership_restriction=has_ownership_restriction
                    )
                    self.session.add(role_permission)
                    logger.info(f"Created role-permission mapping: {role_code} -> {permission_code}")
                else:
                    logger.info(f"Role-permission mapping already exists: {role_code} -> {permission_code}")
        
        await self.session.commit()
    
    async def seed_admin_users(self):
        """Create initial admin users with proper organizational assignments."""
        logger.info("Seeding admin users...")
        
        # Get roles and organizational entities
        roles_result = await self.session.execute(select(Role))
        roles = {role.role_code: role for role in roles_result.scalars().all()}
        
        org_result = await self.session.execute(
            select(Organization).where(Organization.org_code == "VIDYASHAKTHI")
        )
        organization = org_result.scalar_one()
        
        blocks_result = await self.session.execute(select(Block))
        blocks = list(blocks_result.scalars().all())
        
        schools_result = await self.session.execute(select(School))
        schools = list(schools_result.scalars().all())
        
        # Define admin users to create
        admin_users_data = [
            {
                "username": "superadmin",
                "password": "SuperAdmin123!",
                "full_name": "Super Administrator",
                "email": "superadmin@vidyashakthi.edu",
                "phone": "+91-9999999999",
                "role_code": "super_admin",
                "organization_id": None,  # Global access
                "block_id": None,
                "school_id": None
            },
            {
                "username": "vsadmin",
                "password": "VSAdmin123!",
                "full_name": "VidyaShakthi Administrator",
                "email": "admin@vidyashakthi.edu",
                "phone": "+91-9999999998",
                "role_code": "admin",
                "organization_id": organization.id,
                "block_id": None,
                "school_id": None
            },
            {
                "username": "vsoperator",
                "password": "VSOperator123!",
                "full_name": "VidyaShakthi Operator",
                "email": "operator@vidyashakthi.edu",
                "phone": "+91-9999999997",
                "role_code": "admin_user",
                "organization_id": organization.id,
                "block_id": None,
                "school_id": None
            },
            {
                "username": "northblockadmin",
                "password": "BlockAdmin123!",
                "full_name": "North Block Administrator",
                "email": "northblock@vidyashakthi.edu",
                "phone": "+91-9999999996",
                "role_code": "block_admin",
                "organization_id": organization.id,
                "block_id": blocks[0].id if blocks else None,
                "school_id": None
            },
            {
                "username": "southblockadmin",
                "password": "BlockAdmin123!",
                "full_name": "South Block Administrator", 
                "email": "southblock@vidyashakthi.edu",
                "phone": "+91-9999999995",
                "role_code": "block_admin",
                "organization_id": organization.id,
                "block_id": blocks[1].id if len(blocks) > 1 else None,
                "school_id": None
            },
            {
                "username": "schooladmin1",
                "password": "SchoolAdmin123!",
                "full_name": "North Primary School Administrator",
                "email": "northprimary@vidyashakthi.edu",
                "phone": "+91-9999999994",
                "role_code": "teacher",  # Changed from school_admin 
                "organization_id": organization.id,
                "block_id": schools[0].block_id if schools else None,
                "school_id": schools[0].id if schools else None
            },
            {
                "username": "teacher1",
                "password": "Teacher123!",
                "full_name": "John Smith",
                "email": "john.smith@vidyashakthi.edu",
                "phone": "+91-9999999993",
                "role_code": "teacher",
                "organization_id": organization.id,
                "block_id": schools[0].block_id if schools else None,
                "school_id": schools[0].id if schools else None
            },
            {
                "username": "teacher2",
                "password": "Teacher123!",
                "full_name": "Jane Doe",
                "email": "jane.doe@vidyashakthi.edu",
                "phone": "+91-9999999992",
                "role_code": "teacher",
                "organization_id": organization.id,
                "block_id": schools[1].block_id if len(schools) > 1 else None,
                "school_id": schools[1].id if len(schools) > 1 else None
            }
        ]
        
        for user_data in admin_users_data:
            # Check if user already exists
            result = await self.session.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing_user = result.scalar_one_or_none()
            
            if not existing_user:
                role = roles.get(user_data["role_code"])
                if not role:
                    logger.warning(f"Role not found for user {user_data['username']}: {user_data['role_code']}")
                    continue
                
                user = User(
                    username=user_data["username"],
                    hashed_password=get_password_hash(user_data["password"]),
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    phone=user_data["phone"],
                    role_id=role.id,
                    organization_id=user_data["organization_id"],
                    block_id=user_data["block_id"],
                    school_id=user_data["school_id"],
                    is_active=True
                )
                self.session.add(user)
                logger.info(f"Created user: {user_data['username']} ({user_data['full_name']})")
            else:
                logger.info(f"User already exists: {user_data['username']}")
        
        await self.session.commit()


async def main():
    """Main function to run the seeding process."""
    async with RBACDataSeeder() as seeder:
        await seeder.seed_all()


if __name__ == "__main__":
    asyncio.run(main())