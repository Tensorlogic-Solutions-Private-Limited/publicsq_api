from sqlalchemy import Column, Integer, DateTime, func

class AuditMixin:
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  
    created_by = Column(Integer, nullable=True) 
    updated_by = Column(Integer, nullable=True) 
