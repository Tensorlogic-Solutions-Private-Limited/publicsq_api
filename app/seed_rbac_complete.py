"""
Complete RBAC System Seeding Script

This is the master script that orchestrates the complete seeding of the RBAC system.
It runs all seeding operations in the correct order.

Usage:
    python -m app.seed_rbac_complete
    
    Options:
    --minimal    Create minimal test data only
    --force      Force recreate all data (drops existing)
"""

import asyncio
import argparse
from sqlalchemy.future import select
from app.database import AsyncSessionLocal, Base, engine
from app.models.user import Role, User
from app.models.organization import Organization, Block, School
from app.models.permission import Permission, RolePermission
from app.init_rbac_data import RBACDataSeeder
from app.seed_minimal_org import seed_minimal_org
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CompleteSeedingOrchestrator:
    """Orchestrates the complete RBAC seeding process."""
    
    def __init__(self, minimal=False, force=False):
        self.minimal = minimal
        self.force = force
    
    async def check_existing_data(self):
        """Check if RBAC data already exists."""
        async with AsyncSessionLocal() as session:
            # Check for roles
            roles_result = await session.execute(select(Role))
            roles_count = len(list(roles_result.scalars().all()))
            
            # Check for organizations
            orgs_result = await session.execute(select(Organization))
            orgs_count = len(list(orgs_result.scalars().all()))
            
            # Check for permissions
            perms_result = await session.execute(select(Permission))
            perms_count = len(list(perms_result.scalars().all()))
            
            # Check for users
            users_result = await session.execute(select(User))
            users_count = len(list(users_result.scalars().all()))
            
            return {
                "roles": roles_count,
                "organizations": orgs_count,
                "permissions": perms_count,
                "users": users_count
            }
    
    async def clear_existing_data(self):
        """Clear existing RBAC data if force flag is set."""
        if not self.force:
            return
        
        logger.warning("Force flag set - clearing existing RBAC data...")
        
        async with AsyncSessionLocal() as session:
            try:
                # Delete in reverse dependency order
                await session.execute("DELETE FROM role_permissions")
                await session.execute("DELETE FROM permissions")
                await session.execute("DELETE FROM users WHERE role_id IS NOT NULL")
                await session.execute("DELETE FROM schools")
                await session.execute("DELETE FROM blocks")
                await session.execute("DELETE FROM organizations")
                await session.execute("DELETE FROM roles WHERE role_code IN ('super_admin', 'admin', 'admin_user', 'block_admin', 'teacher')")
                
                await session.commit()
                logger.info("Existing RBAC data cleared successfully")
                
            except Exception as e:
                logger.error(f"Error clearing existing data: {e}")
                await session.rollback()
                raise
    
    async def seed_complete_system(self):
        """Seed the complete RBAC system."""
        logger.info("Starting complete RBAC system seeding...")
        
        try:
            # Check existing data
            existing_data = await self.check_existing_data()
            logger.info(f"Existing data counts: {existing_data}")
            
            if any(existing_data.values()) and not self.force:
                logger.warning("RBAC data already exists. Use --force to recreate.")
                response = input("Continue with existing data? (y/N): ")
                if response.lower() != 'y':
                    logger.info("Seeding cancelled by user")
                    return
            
            # Clear existing data if force flag is set
            await self.clear_existing_data()
            
            if self.minimal:
                logger.info("Creating minimal organizational structure...")
                await seed_minimal_org()
            else:
                logger.info("Creating complete RBAC system...")
                async with RBACDataSeeder() as seeder:
                    await seeder.seed_all()
            
            # Verify seeding results
            final_data = await self.check_existing_data()
            logger.info(f"Final data counts: {final_data}")
            
            logger.info("RBAC system seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during complete seeding: {e}")
            raise
    
    async def generate_seeding_report(self):
        """Generate a report of seeded data."""
        logger.info("Generating seeding report...")
        
        async with AsyncSessionLocal() as session:
            # Get roles
            roles_result = await session.execute(select(Role))
            roles = list(roles_result.scalars().all())
            
            # Get organizations
            orgs_result = await session.execute(select(Organization))
            organizations = list(orgs_result.scalars().all())
            
            # Get blocks
            blocks_result = await session.execute(select(Block))
            blocks = list(blocks_result.scalars().all())
            
            # Get schools
            schools_result = await session.execute(select(School))
            schools = list(schools_result.scalars().all())
            
            # Get permissions
            perms_result = await session.execute(select(Permission))
            permissions = list(perms_result.scalars().all())
            
            # Get role-permissions
            role_perms_result = await session.execute(select(RolePermission))
            role_permissions = list(role_perms_result.scalars().all())
            
            # Get users
            users_result = await session.execute(select(User))
            users = list(users_result.scalars().all())
            
            print("\n" + "="*60)
            print("RBAC SEEDING REPORT")
            print("="*60)
            
            print(f"\nROLES ({len(roles)}):")
            for role in roles:
                print(f"  - {role.role_name} ({role.role_code})")
            
            print(f"\nORGANIZATIONS ({len(organizations)}):")
            for org in organizations:
                print(f"  - {org.org_name} ({org.org_code})")
            
            print(f"\nBLOCKS ({len(blocks)}):")
            for block in blocks:
                print(f"  - {block.block_name} ({block.block_code})")
            
            print(f"\nSCHOOLS ({len(schools)}):")
            for school in schools:
                print(f"  - {school.school_name} ({school.udise_code})")
            
            print(f"\nPERMISSIONS ({len(permissions)}):")
            for perm in permissions:
                print(f"  - {perm.permission_name} ({perm.permission_code})")
            
            print(f"\nROLE-PERMISSION MAPPINGS: {len(role_permissions)}")
            
            print(f"\nUSERS ({len(users)}):")
            for user in users:
                role_name = user.role.role_name if user.role else "No Role"
                org_name = user.organization.org_name if user.organization else "No Org"
                print(f"  - {user.username} ({user.full_name}) - {role_name} @ {org_name}")
            
            print("\n" + "="*60)


async def main():
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(description="Complete RBAC System Seeding")
    parser.add_argument("--minimal", action="store_true", help="Create minimal test data only")
    parser.add_argument("--force", action="store_true", help="Force recreate all data")
    parser.add_argument("--report", action="store_true", help="Generate seeding report only")
    
    args = parser.parse_args()
    
    orchestrator = CompleteSeedingOrchestrator(minimal=args.minimal, force=args.force)
    
    if args.report:
        await orchestrator.generate_seeding_report()
    else:
        await orchestrator.seed_complete_system()
        await orchestrator.generate_seeding_report()


if __name__ == "__main__":
    asyncio.run(main())