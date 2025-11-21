"""
Comprehensive logging utilities for RBAC system.
"""
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from app.models.user import User


class LogLevel(Enum):
    """Log levels for RBAC events."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RBACEventType(Enum):
    """Types of RBAC events to log."""
    PERMISSION_CHECK = "permission_check"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    SCOPE_VALIDATION = "scope_validation"
    SCOPE_VIOLATION = "scope_violation"
    OWNERSHIP_CHECK = "ownership_check"
    OWNERSHIP_VIOLATION = "ownership_violation"
    USER_CONTEXT_LOADED = "user_context_loaded"
    CACHE_OPERATION = "cache_operation"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"


class RBACLogger:
    """Comprehensive logger for RBAC operations."""
    
    def __init__(self, logger_name: str = "rbac"):
        self.logger = logging.getLogger(logger_name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with appropriate formatting."""
        if not self.logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)
    
    def _create_log_entry(
        self,
        event_type: RBACEventType,
        user_id: Optional[int] = None,
        permission: Optional[str] = None,
        resource_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        granted: Optional[bool] = None,
        reason: Optional[str] = None,
        scope_info: Optional[Dict[str, Any]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create structured log entry."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "permission": permission,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "action": action,
            "granted": granted,
            "reason": reason,
            "scope_info": scope_info or {},
            "additional_data": additional_data or {}
        }
        
        # Remove None values
        return {k: v for k, v in log_entry.items() if v is not None}
    
    def log_permission_check(
        self,
        user_id: int,
        permission: str,
        granted: bool,
        resource_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        reason: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log permission check result."""
        event_type = RBACEventType.PERMISSION_GRANTED if granted else RBACEventType.PERMISSION_DENIED
        
        log_entry = self._create_log_entry(
            event_type=event_type,
            user_id=user_id,
            permission=permission,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            granted=granted,
            reason=reason,
            additional_data=additional_data
        )
        
        if granted:
            self.logger.info(f"Permission granted: {json.dumps(log_entry)}")
        else:
            self.logger.warning(f"Permission denied: {json.dumps(log_entry)}")
    
    def log_scope_validation(
        self,
        user_id: int,
        valid: bool,
        user_scope: Optional[Dict[str, Any]] = None,
        attempted_scope: Optional[Dict[str, Any]] = None,
        violation_type: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Log scope validation result."""
        event_type = RBACEventType.SCOPE_VALIDATION if valid else RBACEventType.SCOPE_VIOLATION
        
        scope_info = {
            "user_scope": user_scope or {},
            "attempted_scope": attempted_scope or {},
            "violation_type": violation_type
        }
        
        log_entry = self._create_log_entry(
            event_type=event_type,
            user_id=user_id,
            granted=valid,
            reason=reason,
            scope_info=scope_info
        )
        
        if valid:
            self.logger.info(f"Scope validation passed: {json.dumps(log_entry)}")
        else:
            self.logger.warning(f"Scope violation detected: {json.dumps(log_entry)}")
    
    def log_ownership_check(
        self,
        user_id: int,
        resource_id: int,
        resource_type: str,
        resource_owner_id: int,
        action: str,
        allowed: bool,
        reason: Optional[str] = None
    ):
        """Log ownership check result."""
        event_type = RBACEventType.OWNERSHIP_CHECK if allowed else RBACEventType.OWNERSHIP_VIOLATION
        
        additional_data = {
            "resource_owner_id": resource_owner_id,
            "ownership_match": user_id == resource_owner_id
        }
        
        log_entry = self._create_log_entry(
            event_type=event_type,
            user_id=user_id,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            granted=allowed,
            reason=reason,
            additional_data=additional_data
        )
        
        if allowed:
            self.logger.info(f"Ownership check passed: {json.dumps(log_entry)}")
        else:
            self.logger.warning(f"Ownership violation detected: {json.dumps(log_entry)}")
    
    def log_user_context_loaded(
        self,
        user_id: int,
        role_code: Optional[str] = None,
        permissions_count: int = 0,
        organizational_scope: Optional[Dict[str, Any]] = None,
        cached: bool = False
    ):
        """Log user context loading."""
        additional_data = {
            "role_code": role_code,
            "permissions_count": permissions_count,
            "cached": cached
        }
        
        log_entry = self._create_log_entry(
            event_type=RBACEventType.USER_CONTEXT_LOADED,
            user_id=user_id,
            scope_info=organizational_scope or {},
            additional_data=additional_data
        )
        
        self.logger.info(f"User context loaded: {json.dumps(log_entry)}")
    
    def log_cache_operation(
        self,
        operation: str,
        user_id: Optional[int] = None,
        cache_key: Optional[str] = None,
        hit: Optional[bool] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log cache operations."""
        cache_data = {
            "operation": operation,
            "cache_key": cache_key,
            "hit": hit
        }
        
        # Merge with additional data if provided
        if additional_data:
            cache_data.update(additional_data)
        
        log_entry = self._create_log_entry(
            event_type=RBACEventType.CACHE_OPERATION,
            user_id=user_id,
            additional_data=cache_data
        )
        
        self.logger.debug(f"Cache operation: {json.dumps(log_entry)}")
    
    def log_authentication_failure(
        self,
        reason: str,
        user_identifier: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log authentication failures."""
        log_entry = self._create_log_entry(
            event_type=RBACEventType.AUTHENTICATION_FAILURE,
            reason=reason,
            additional_data={
                "user_identifier": user_identifier,
                **(additional_data or {})
            }
        )
        
        self.logger.warning(f"Authentication failure: {json.dumps(log_entry)}")
    
    def log_authorization_failure(
        self,
        user_id: int,
        endpoint: str,
        method: str,
        reason: str,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log authorization failures."""
        log_entry = self._create_log_entry(
            event_type=RBACEventType.AUTHORIZATION_FAILURE,
            user_id=user_id,
            reason=reason,
            additional_data={
                "endpoint": endpoint,
                "method": method,
                **(additional_data or {})
            }
        )
        
        self.logger.warning(f"Authorization failure: {json.dumps(log_entry)}")
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        severity: str = "medium",
        description: str = "",
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log security-related events."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "security_event",
            "security_event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "description": description,
            "additional_data": additional_data or {}
        }
        
        if severity in ["high", "critical"]:
            self.logger.error(f"Security event: {json.dumps(log_entry)}")
        else:
            self.logger.warning(f"Security event: {json.dumps(log_entry)}")
    
    def log_audit_trail(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        success: bool = True
    ):
        """Log audit trail for important actions."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "audit_trail",
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_values": old_values or {},
            "new_values": new_values or {},
            "success": success
        }
        
        self.logger.info(f"Audit trail: {json.dumps(log_entry)}")


# Global RBAC logger instance
rbac_logger = RBACLogger()


# Convenience functions for backward compatibility
def log_permission_check(user_id: int, permission: str, granted: bool, reason: str = None):
    """Log permission check result."""
    rbac_logger.log_permission_check(user_id, permission, granted, reason=reason)


def log_scope_violation(user_id: int, attempted_resource: str, user_scope: str):
    """Log scope violation."""
    rbac_logger.log_scope_validation(
        user_id=user_id,
        valid=False,
        attempted_scope={"resource": attempted_resource},
        user_scope={"scope": user_scope},
        reason="Scope violation detected"
    )