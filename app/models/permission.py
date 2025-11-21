from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.audit_mixin import AuditMixin


class Permission(Base, AuditMixin):
    """
    Permission model representing individual permissions in the system.
    Each permission defines a specific action that can be performed on a resource.
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    permission_code = Column(String, unique=True, nullable=False, index=True)
    permission_name = Column(String, unique=True, nullable=False)
    permission_description = Column(Text, nullable=True)
    resource_type = Column(String, nullable=False)  # e.g., 'question_bank', 'quiz', 'user', 'school'
    action_type = Column(String, nullable=False)    # e.g., 'create', 'read', 'update', 'delete'

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Permission(id={self.id}, code='{self.permission_code}', resource='{self.resource_type}', action='{self.action_type}')>"


class RolePermission(Base, AuditMixin):
    """
    Junction table linking roles to permissions with additional metadata.
    Supports ownership restrictions for certain permissions.
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="SET NULL"), nullable=False)
    has_ownership_restriction = Column(Boolean, default=False, nullable=False)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    # Unique constraint on role_id and permission_id combination
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
        {"extend_existing": True}
    )

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id}, ownership_restriction={self.has_ownership_restriction})>"