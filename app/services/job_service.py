"""
Service layer for upload job management operations.
"""
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.master import UploadJob, JobStatusEnum
from app.models.user import User


class JobService:
    """Service for managing upload job operations."""
    
    @staticmethod
    async def create_upload_job(
        filename: str,
        user_id: int,
        db: AsyncSession
    ) -> str:
        """
        Create a new upload job record.
        
        Args:
            filename: Name of the uploaded file
            user_id: ID of the user creating the job
            db: Database session
            
        Returns:
            str: The generated job ID (UUID)
        """
        job_id = str(uuid.uuid4())
        
        upload_job = UploadJob(
            id=job_id,
            user_id=user_id,
            filename=filename,
            status=JobStatusEnum.PENDING,
            total_rows=None,
            processed_rows=0,
            success_count=0,
            error_count=0,
            error_details=None,
            result_message=None,
            started_at=None,
            completed_at=None,
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(upload_job)
        await db.commit()
        await db.refresh(upload_job)
        
        return job_id
    
    @staticmethod
    async def get_job_status(
        job_id: str,
        db: AsyncSession
    ) -> Optional[UploadJob]:
        """
        Get upload job by ID.
        
        Args:
            job_id: The job ID to retrieve
            db: Database session
            
        Returns:
            Optional[UploadJob]: The upload job if found, None otherwise
        """
        result = await db.execute(
            select(UploadJob)
            .options(selectinload(UploadJob.user))
            .filter(UploadJob.id == job_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_job_status(
        job_id: str,
        status: JobStatusEnum,
        db: AsyncSession
    ) -> None:
        """
        Update the status of an upload job.
        
        Args:
            job_id: The job ID to update
            status: New status to set
            db: Database session
        """
        update_data = {"status": status}
        
        # Set started_at when status changes to PROCESSING
        if status == JobStatusEnum.PROCESSING:
            update_data["started_at"] = datetime.utcnow()
        
        # Set completed_at when status changes to COMPLETED or FAILED
        elif status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED]:
            update_data["completed_at"] = datetime.utcnow()
        
        await db.execute(
            update(UploadJob)
            .where(UploadJob.id == job_id)
            .values(**update_data)
        )
        await db.commit()
    
    @staticmethod
    async def update_job_progress(
        job_id: str,
        processed: int,
        success: int,
        errors: int,
        total_rows: Optional[int] = None,
        db: AsyncSession = None
    ) -> None:
        """
        Update the progress of an upload job.
        
        Args:
            job_id: The job ID to update
            processed: Number of rows processed so far
            success: Number of successful rows
            errors: Number of error rows
            total_rows: Total number of rows (optional, set only if provided)
            db: Database session
        """
        update_data = {
            "processed_rows": processed,
            "success_count": success,
            "error_count": errors
        }
        
        if total_rows is not None:
            update_data["total_rows"] = total_rows
        
        await db.execute(
            update(UploadJob)
            .where(UploadJob.id == job_id)
            .values(**update_data)
        )
        await db.commit()
    
    @staticmethod
    async def complete_job(
        job_id: str,
        result_message: str,
        error_details: Optional[Dict[str, Any]],
        db: AsyncSession,
        result_loc: Optional[str] = None
    ) -> None:
        """
        Mark a job as completed with final results.
        
        Args:
            job_id: The job ID to complete
            result_message: Final result message
            error_details: Dictionary containing error details (optional)
            db: Database session
            result_loc: S3 URL of the result file (optional)
        """
        update_values = {
            "status": JobStatusEnum.COMPLETED,
            "result_message": result_message,
            "error_details": error_details,
            "completed_at": datetime.utcnow()
        }
        
        if result_loc:
            update_values["result_loc"] = result_loc
        
        await db.execute(
            update(UploadJob)
            .where(UploadJob.id == job_id)
            .values(**update_values)
        )
        await db.commit()
    
    @staticmethod
    async def fail_job(
        job_id: str,
        error_message: str,
        db: AsyncSession
    ) -> None:
        """
        Mark a job as failed with error message.
        
        Args:
            job_id: The job ID to fail
            error_message: Error message describing the failure
            db: Database session
        """
        await db.execute(
            update(UploadJob)
            .where(UploadJob.id == job_id)
            .values(
                status=JobStatusEnum.FAILED,
                result_message=error_message,
                completed_at=datetime.utcnow()
            )
        )
        await db.commit()
    
    @staticmethod
    async def cleanup_job_file(
        job_id: str,
        file_path: str,
        db: AsyncSession
    ) -> bool:
        """
        Clean up the uploaded file after job processing.
        
        Args:
            job_id: The job ID for logging purposes
            file_path: Path to the file to delete
            db: Database session
            
        Returns:
            bool: True if file was successfully deleted, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            # Log the error but don't fail the job completion
            # TODO: Replace with proper logging in production
            return False
    
    @staticmethod
    async def get_user_jobs(
        user_id: int,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        status_filter: Optional[JobStatusEnum] = None
    ) -> List[UploadJob]:
        """
        Get upload jobs for a specific user with optional filtering.
        
        Args:
            user_id: ID of the user
            db: Database session
            page: Page number for pagination
            page_size: Number of items per page
            status_filter: Optional status to filter by
            
        Returns:
            List[UploadJob]: List of upload jobs
        """
        query = select(UploadJob).filter(UploadJob.user_id == user_id)
        
        if status_filter:
            query = query.filter(UploadJob.status == status_filter)
        
        # Order by creation date (newest first)
        query = query.order_by(UploadJob.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_job_with_user_validation(
        job_id: str,
        user_id: int,
        db: AsyncSession
    ) -> Optional[UploadJob]:
        """
        Get upload job by ID with user validation.
        
        Args:
            job_id: The job ID to retrieve
            user_id: ID of the user requesting the job
            db: Database session
            
        Returns:
            Optional[UploadJob]: The upload job if found and user has access, None otherwise
        """
        result = await db.execute(
            select(UploadJob)
            .options(selectinload(UploadJob.user))
            .filter(UploadJob.id == job_id)
            .filter(UploadJob.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_jobs(
        db: AsyncSession,
        filename: Optional[str] = None
    ) -> List[UploadJob]:
        """
        Get all upload jobs from all users (admin function) with optional filename partial match.
        Args:
            db: Database session
            filename: Optional partial filename to filter (case-insensitive)
        Returns:
            List[UploadJob]: List of all upload jobs ordered by creation date (newest first)
        """
        query = select(UploadJob).options(selectinload(UploadJob.user))

        if filename:
            # Use ILIKE for case-insensitive partial match (Postgres). This will work on most DBs that support ilike.
            query = query.filter(UploadJob.filename.ilike(f"%{filename}%"))

        query = query.order_by(UploadJob.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def get_jobs_by_status(
        status: str,
        db: AsyncSession,
        filename: Optional[str] = None
    ) -> List[UploadJob]:
        """
        Get upload jobs filtered by status with optional filename partial match.
        Args:
            status: Status to filter by (pending, processing, completed, failed)
            db: Database session
            filename: Optional partial filename to filter (case-insensitive)
        Returns:
            List[UploadJob]: List of upload jobs with the specified status
        """
        from app.models.master import JobStatusEnum

        # Convert string status to enum
        try:
            status_enum = JobStatusEnum(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: pending, processing, completed, failed"
            )

        query = select(UploadJob).options(selectinload(UploadJob.user)).filter(UploadJob.status == status_enum)

        if filename:
            query = query.filter(UploadJob.filename.ilike(f"%{filename}%"))

        query = query.order_by(UploadJob.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def get_jobs_by_username(
        username: str,
        db: AsyncSession,
        filename: Optional[str] = None
    ) -> List[UploadJob]:
        """
        Get upload jobs filtered by username with optional filename partial match.
        Args:
            username: Username to filter by (case-insensitive)
            db: Database session
            filename: Optional partial filename to filter (case-insensitive)
        Returns:
            List[UploadJob]: List of upload jobs for the specified user
        """
        from app.models.user import User

        # case-insensitive username match
        query = (
            select(UploadJob)
            .join(User, UploadJob.user_id == User.id)
            .options(selectinload(UploadJob.user))
            .filter(func.lower(User.username) == username.lower())
        )

        if filename:
            query = query.filter(UploadJob.filename.ilike(f"%{filename}%"))

        query = query.order_by(UploadJob.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()


    @staticmethod
    async def get_jobs_by_username_and_status(
        username: str,
        status: str,
        db: AsyncSession,
        filename: Optional[str] = None
    ) -> List[UploadJob]:
        """
        Get upload jobs filtered by both username and status with optional filename partial match.
        Args:
            username: Username to filter by (case-insensitive)
            status: Status to filter by (pending, processing, completed, failed)
            db: Database session
            filename: Optional partial filename to filter (case-insensitive)
        Returns:
            List[UploadJob]: List of upload jobs for the specified user and status
        """
        from app.models.user import User
        from app.models.master import JobStatusEnum

        # Convert string status to enum
        try:
            status_enum = JobStatusEnum(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: pending, processing, completed, failed"
            )

        query = (
            select(UploadJob)
            .join(User, UploadJob.user_id == User.id)
            .options(selectinload(UploadJob.user))
            .filter(func.lower(User.username) == username.lower())
            .filter(UploadJob.status == status_enum)
        )

        if filename:
            query = query.filter(UploadJob.filename.ilike(f"%{filename}%"))

        query = query.order_by(UploadJob.created_at.desc())

        result = await db.execute(query)
        return result.scalars().all()
