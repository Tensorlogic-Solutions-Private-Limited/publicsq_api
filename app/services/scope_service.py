"""
Hierarchical scope filtering service for RBAC system.
"""
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Query

from app.models.user import User
from app.models.organization import Organization, Block, School
from app.middleware.rbac import rbac_middleware


class ScopeFilterService:
    """Service for applying hierarchical scope filtering to database queries."""
    
    @staticmethod
    async def filter_organizations_query(db, user: User, query):
        """Apply scope filtering to organizations query."""
        scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
        
        if not scope_filter:  # Super admin - no filtering
            return query
        
        if "organization_id" in scope_filter:
            return query.filter(Organization.id == scope_filter["organization_id"])
        
        # If no organization access, return empty result
        return query.filter(Organization.id == -1)
    
    @staticmethod
    async def filter_blocks_query(db, user: User, query):
        """Apply scope filtering to blocks query."""
        scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
        
        if not scope_filter:  # Super admin - no filtering
            return query
        
        if "organization_id" in scope_filter:
            return query.filter(Block.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            return query.filter(Block.id == scope_filter["block_id"])
        
        # If no access, return empty result
        return query.filter(Block.id == -1)
    
    @staticmethod
    async def filter_schools_query(db, user: User, query):
        """Apply scope filtering to schools query."""
        scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
        
        if not scope_filter:  # Super admin - no filtering
            return query
        
        if "organization_id" in scope_filter:
            return query.filter(School.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            return query.filter(School.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            return query.filter(School.id == scope_filter["school_id"])
        
        # If no access, return empty result
        return query.filter(School.id == -1)
    
    @staticmethod
    async def filter_users_query(db, user: User, query):
        """Apply scope filtering to users query with role hierarchy."""
        scope_filter = await rbac_middleware.get_user_scope_filter_with_role_hierarchy(db, user)
        
        if not scope_filter:  # Super admin - no filtering
            return query
        
        # Apply organizational scope filtering
        if "organization_id" in scope_filter:
            query = query.filter(User.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            # Block admin sees users in their block (including sub-levels)
            query = query.filter(User.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            # School admin/teacher sees users in their school
            query = query.filter(User.school_id == scope_filter["school_id"])
        
        # Apply role hierarchy filtering
        if "allowed_roles" in scope_filter:
            from app.models.user import Role
            allowed_roles = scope_filter["allowed_roles"]
            query = query.join(Role).filter(Role.role_code.in_(allowed_roles))
        
        # If no access, return empty result
        if "id" in scope_filter and scope_filter["id"] == -1:
            return query.filter(User.id == -1)
        
        return query
    
    @staticmethod
    async def filter_questions_query(db, user: User, query):
        """Apply scope filtering to questions query."""
        scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
        
        if not scope_filter:  # Super admin - no filtering
            return query
        
        # Import Questions model to access columns
        from app.models.master import Questions
        
        # Apply scope filtering using Questions model columns
        if "organization_id" in scope_filter:
            return query.filter(Questions.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            return query.filter(Questions.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            return query.filter(Questions.school_id == scope_filter["school_id"])
        
        # If no access, return empty result
        return query.filter(Questions.id == -1)
    
    @staticmethod
    async def get_accessible_organization_ids(db, user: User) -> List[int]:
        """Get list of organization IDs accessible to the user."""
        user_context = await rbac_middleware.load_user_context(db, user)
        
        if user_context.is_super_admin():
            # Super admin can access all organizations
            query = select(Organization.id)
            result = await db.execute(query)
            return result.scalars().all()
        
        if user_context.is_admin() or user_context.is_admin_user():
            # Admin and Admin-User can access their organization
            org_id = user_context.organizational_scope["organization_id"]
            return [org_id] if org_id else []
        
        # Block admin, school admin, and teachers can access their organization
        org_id = user_context.organizational_scope["organization_id"]
        return [org_id] if org_id else []
    
    @staticmethod
    async def get_accessible_block_ids(db, user: User) -> List[int]:
        """Get list of block IDs accessible to the user."""
        user_context = await rbac_middleware.load_user_context(db, user)
        
        if user_context.is_super_admin():
            # Super admin can access all blocks
            query = select(Block.id)
            result = await db.execute(query)
            return result.scalars().all()
        
        if user_context.is_admin() or user_context.is_admin_user():
            # Admin and Admin-User can access blocks in their organization
            org_id = user_context.organizational_scope["organization_id"]
            if org_id:
                query = select(Block.id).filter(Block.organization_id == org_id)
                result = await db.execute(query)
                return result.scalars().all()
            return []
        
        if user_context.is_block_admin():
            # Block admin can access their block
            block_id = user_context.organizational_scope["block_id"]
            return [block_id] if block_id else []
        
        # School admin and teachers can access their block
        block_id = user_context.organizational_scope["block_id"]
        return [block_id] if block_id else []
    
    @staticmethod
    async def get_accessible_school_ids(db, user: User) -> List[int]:
        """Get list of school IDs accessible to the user."""
        user_context = await rbac_middleware.load_user_context(db, user)
        
        if user_context.is_super_admin():
            # Super admin can access all schools
            query = select(School.id)
            result = await db.execute(query)
            return result.scalars().all()
        
        if user_context.is_admin() or user_context.is_admin_user():
            # Admin and Admin-User can access schools in their organization
            org_id = user_context.organizational_scope["organization_id"]
            if org_id:
                query = select(School.id).filter(School.organization_id == org_id)
                result = await db.execute(query)
                return result.scalars().all()
            return []
        
        if user_context.is_block_admin():
            # Block admin can access schools in their block
            block_id = user_context.organizational_scope["block_id"]
            if block_id:
                query = select(School.id).filter(School.block_id == block_id)
                result = await db.execute(query)
                return result.scalars().all()
            return []
        
        # School admin and teachers can access their school
        school_id = user_context.organizational_scope["school_id"]
        return [school_id] if school_id else []
    
    @staticmethod
    async def can_access_organization(db, user: User, organization_id: int) -> bool:
        """Check if user can access a specific organization."""
        # First check if organization exists
        from app.models.organization import Organization
        query = select(Organization).filter(Organization.id == organization_id, Organization.is_active == True)
        result = await db.execute(query)
        org_exists = result.scalar_one_or_none() is not None
        
        if not org_exists:
            return False  # Organization doesn't exist or is inactive
        
        accessible_org_ids = await ScopeFilterService.get_accessible_organization_ids(db, user)
        return organization_id in accessible_org_ids
    
    @staticmethod
    async def can_access_block(db, user: User, block_id: int) -> bool:
        """Check if user can access a specific block."""
        # First check if block exists
        from app.models.organization import Block
        query = select(Block).filter(Block.id == block_id, Block.is_active == True)
        result = await db.execute(query)
        block_exists = result.scalar_one_or_none() is not None
        
        if not block_exists:
            return False  # Block doesn't exist or is inactive
        
        accessible_block_ids = await ScopeFilterService.get_accessible_block_ids(db, user)
        return block_id in accessible_block_ids
    
    @staticmethod
    async def can_access_school(db, user: User, school_id: int) -> bool:
        """Check if user can access a specific school."""
        # First check if school exists
        from app.models.organization import School
        query = select(School).filter(School.id == school_id, School.is_active == True)
        result = await db.execute(query)
        school_exists = result.scalar_one_or_none() is not None
        
        if not school_exists:
            return False  # School doesn't exist or is inactive
        
        accessible_school_ids = await ScopeFilterService.get_accessible_school_ids(db, user)
        return school_id in accessible_school_ids