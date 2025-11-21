"""
Permission Seeding Script Based on CSV Matrix

This script creates permissions and role-permission mappings based on the exact
role_permissions.csv file structure.

Usage:
    python -m app.seed_permissions_from_csv
"""

import asyncio
import csv
from pathlib import Path
from sqlalchemy.future import select
from app.database import AsyncSessionLocal, Base, engine
from app.models.user import Role
from app.models.permission import Permission, RolePermission
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PermissionSeeder:
    """Class to seed permissions from CSV matrix."""
    
    def __init__(self):
        self.session = None
        self.csv_file_path = Path("role_permissions.csv")
    
    async def __aenter__(self):
        self.session = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def parse_csv_matrix(self):
        """Parse the CSV file and extract permission mappings."""
        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_file_path}")
        
        permissions_data = []
        role_permissions = {}
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader)  # Get role headers
            
            # Map CSV role names to our role codes
            role_mapping = {
                "Super Admin/Support Team": "super_admin",
                "VidyaShakthi Admin": "admin",  # Changed to generic admin
                "VidhyaShakti Operator": "admin_user",  # Changed to generic admin_user
                "Block Admin": "block_admin",
                "Teacher": "teacher"
                # Note: School Admin role removed for MVP
            }
            
            current_category = None
            
            for row in reader:
                if not row or not row[0].strip():
                    continue
                
                feature_name = row[0].strip()
                
                # Skip category headers and empty rows
                if feature_name in ["Question Bank", "Quiz", "Admin Users", "School", "Teachers"]:
                    current_category = feature_name
                    continue
                
                if not feature_name or feature_name.startswith(",,"):
                    continue
                
                # Generate permission data
                permission_code = self.generate_permission_code(feature_name, current_category)
                if permission_code:
                    resource_type, action_type = self.extract_resource_action(feature_name, current_category)
                    
                    permission_data = {
                        "permission_code": permission_code,
                        "permission_name": feature_name,
                        "permission_description": f"Permission to {feature_name.lower()}",
                        "resource_type": resource_type,
                        "action_type": action_type
                    }
                    permissions_data.append(permission_data)
                    
                    # Process role permissions for this feature
                    for i, cell_value in enumerate(row[1:], 1):
                        if i < len(headers):
                            role_name = headers[i].strip()
                            role_code = role_mapping.get(role_name)
                            
                            if role_code and cell_value.strip():
                                has_ownership = "added by them" in cell_value.lower()
                                has_permission = cell_value.strip().upper() == "Y" or "added by them" in cell_value.lower()
                                
                                if has_permission:
                                    if role_code not in role_permissions:
                                        role_permissions[role_code] = []
                                    
                                    role_permissions[role_code].append({
                                        "permission_code": permission_code,
                                        "has_ownership_restriction": has_ownership
                                    })
        
        return permissions_data, role_permissions
    
    def generate_permission_code(self, feature_name, category):
        """Generate permission code from feature name and category."""
        if not feature_name:
            return None
        
        # Map categories to resource types
        category_mapping = {
            "Question Bank": "question_bank",
            "Quiz": "quiz", 
            "Admin Users": "user",
            "School": "school",
            "Teachers": "teacher"
            # Note: School Admin removed for MVP
        }
        
        resource = category_mapping.get(category, "unknown")
        
        # Map feature names to actions
        feature_lower = feature_name.lower()
        
        if "upload" in feature_lower:
            action = "upload"
        elif "create" in feature_lower:
            action = "create"
        elif "view" in feature_lower or "list" in feature_lower or "details" in feature_lower:
            action = "view" if "view" in feature_lower else ("list" if "list" in feature_lower else "view")
        elif "edit" in feature_lower:
            if "properties" in feature_lower:
                action = "edit_properties"
            elif "questions" in feature_lower:
                action = "edit_questions"
            else:
                action = "edit"
        elif "delete" in feature_lower or "delet" in feature_lower:
            if "questions" in feature_lower:
                action = "delete_questions"
            else:
                action = "delete"
        elif "conduct" in feature_lower:
            action = "conduct"
        else:
            action = "unknown"
        
        return f"{resource}.{action}"
    
    def extract_resource_action(self, feature_name, category):
        """Extract resource type and action type from feature name and category."""
        category_mapping = {
            "Question Bank": "question_bank",
            "Quiz": "quiz",
            "Admin Users": "user", 
            "School": "school",
            "Teachers": "teacher"
            # Note: School Admin removed for MVP
        }
        
        resource_type = category_mapping.get(category, "unknown")
        
        feature_lower = feature_name.lower()
        if "upload" in feature_lower or "create" in feature_lower:
            action_type = "create"
        elif "view" in feature_lower or "list" in feature_lower or "details" in feature_lower:
            action_type = "read"
        elif "edit" in feature_lower:
            action_type = "update"
        elif "delete" in feature_lower or "delet" in feature_lower:
            action_type = "delete"
        elif "conduct" in feature_lower:
            action_type = "execute"
        else:
            action_type = "unknown"
        
        return resource_type, action_type
    
    async def seed_permissions(self, permissions_data):
        """Create permissions in the database."""
        logger.info("Seeding permissions from CSV...")
        
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
    
    async def seed_role_permissions(self, role_permissions_data):
        """Create role-permission mappings."""
        logger.info("Seeding role-permission mappings from CSV...")
        
        # Get all roles and permissions
        roles_result = await self.session.execute(select(Role))
        roles = {role.role_code: role for role in roles_result.scalars().all()}
        
        permissions_result = await self.session.execute(select(Permission))
        permissions = {perm.permission_code: perm for perm in permissions_result.scalars().all()}
        
        for role_code, permission_mappings in role_permissions_data.items():
            role = roles.get(role_code)
            if not role:
                logger.warning(f"Role not found: {role_code}")
                continue
            
            for mapping in permission_mappings:
                permission_code = mapping["permission_code"]
                has_ownership_restriction = mapping["has_ownership_restriction"]
                
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
    
    async def seed_from_csv(self):
        """Main method to seed permissions from CSV file."""
        try:
            # Ensure database tables exist
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Parse CSV file
            permissions_data, role_permissions_data = self.parse_csv_matrix()
            
            # Seed permissions and role-permission mappings
            await self.seed_permissions(permissions_data)
            await self.seed_role_permissions(role_permissions_data)
            
            logger.info("Successfully seeded permissions from CSV!")
            
        except Exception as e:
            logger.error(f"Error seeding permissions from CSV: {e}")
            await self.session.rollback()
            raise


async def main():
    """Main function to run the CSV-based permission seeding."""
    async with PermissionSeeder() as seeder:
        await seeder.seed_from_csv()


if __name__ == "__main__":
    asyncio.run(main())