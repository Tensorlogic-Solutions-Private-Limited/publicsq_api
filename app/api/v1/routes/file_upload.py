from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.data_upload_service import generate_excel_template
from app.services.enhanced_upload_service import enhanced_upload_service
from app.services.job_service import JobService
from app.api.v1.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.upload import JobStatusResponseSchema, JobListResponseSchema
from pydantic import BaseModel
import shutil
import os
import uuid
from app.utils.get_user_role import get_user_role
from app.decorators.permissions import require_permission
from typing import Dict, Any

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class UploadJobCreatedResponse(BaseModel):
    """Response schema for successful upload job creation."""
    job_id: str
    message: str
    status_endpoint: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Upload job created successfully. Use the job_id to check processing status.",
                "status_endpoint": "/v1/upload-jobs/123e4567-e89b-12d3-a456-426614174000"
            }
        }

@router.post("/v1/upload-excel", response_model=UploadJobCreatedResponse, tags=["Bulk Upload"])
@require_permission("question_bank.upload")
async def upload_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload an Excel file to bulk insert questions into the database using async processing.

    This endpoint initiates an asynchronous bulk upload process that processes Excel files
    containing question data. The upload is processed in the background, allowing users
    to track progress and retrieve results using the returned job ID.

    ## Async Job Processing Flow

    1. **File Upload**: Submit Excel file to this endpoint
    2. **Job Creation**: System creates a job record and returns job_id immediately
    3. **Background Processing**: File is processed asynchronously in the background
    4. **Status Tracking**: Use GET /v1/upload-jobs/{job_id} to monitor progress
    5. **Completion**: Job status becomes 'completed' or 'failed' with detailed results

    ## Template Structure

    The new Excel template supports enhanced question categorization:

    ### Required Columns:
    - `Question_text`: The question content
    - `answer_option_A`, `answer_option_B`, `answer_option_C`, `answer_option_D`: Answer choices
    - `correct_answer`: Correct answer (A, B, C, or D)
    - `chapter_name`: Chapter name for the question
    - `topic_name`: Topic name within the chapter
    - `subtopic_name`: Subtopic name within the topic
    - `Medium`: Language medium (e.g., English, Hindi)
    - `Board`: Educational board (e.g., CBSE, ICSE)
    - `State`: State/region (e.g., Delhi, Maharashtra)
    - `Class`: Grade/standard (e.g., 10, 12)
    - `Subject`: Subject name (must exist in database)
    - `cognitive_learning`: Learning type (Understanding, Information)
    - `difficulty`: Question difficulty (Easy, Medium, Hard)

    ## Automatic Code Generation

    The system automatically generates:
    - **Question IDs**: Format Q{sequential_number}
    - **Chapter Codes**: Format C{3-digit-number} (C000, C001, etc.)
    - **Topic Codes**: Format T{3-digit-number} (T000, T001, etc.)
    - **Subtopic Codes**: Format S{3-digit-number} (S000, S001, etc.)
    - **Taxonomy Codes**: Format TAX{chapter_code}{topic_code}{subtopic_code}

    ## Master Data Handling

    - **Auto-Creation**: Board, State, and Medium entries are created automatically if not found
    - **Lookup Required**: Subject, Cognitive Learning, and Difficulty must exist in database
    - **Text Normalization**: All text is normalized (trimmed, case-insensitive lookup)

    ## Error Handling

    - **Row-Level Processing**: Invalid rows are skipped, processing continues
    - **Detailed Error Reporting**: Each error includes row number, type, and description
    - **Organizational Context**: Questions are automatically associated with user's organization

    ## Response Format

    ```json
    {
      "job_id": "123e4567-e89b-12d3-a456-426614174000",
      "message": "Upload job created successfully. Use the job_id to check processing status.",
      "status_endpoint": "/v1/upload-jobs/123e4567-e89b-12d3-a456-426614174000"
    }
    ```

    ## Example Workflow

    ```python
    # 1. Upload file
    response = requests.post("/v1/upload-excel", files={"file": excel_file})
    job_id = response.json()["job_id"]

    # 2. Poll for status
    while True:
        status_response = requests.get(f"/v1/upload-jobs/{job_id}")
        status = status_response.json()["status"]
        
        if status in ["completed", "failed"]:
            break
        
        time.sleep(2)  # Wait 2 seconds before next check

    # 3. Get final results
    final_result = status_response.json()
    print(f"Success: {final_result['success_count']}, Errors: {final_result['error_count']}")
    ```

    - **Permission Required**: question_bank.upload
    - **File Format**: Must be `.xls` or `.xlsx` with the new template structure
    - **File Size Limit**: Recommended maximum 10MB for optimal performance
    - **Returns**: Job ID for tracking upload progress and results
    - **Processing Time**: Varies based on file size (typically 1-5 minutes for 1000 rows)
    """
    # Validate file type
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Invalid file format. Only Excel files are allowed.")

    # Generate unique filename to avoid conflicts
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create upload job record
        job_id = await JobService.create_upload_job(
            filename=file.filename,
            user_id=current_user.id,
            db=db
        )
        
        # Start async processing in background
        background_tasks.add_task(
            enhanced_upload_service.process_excel_upload_async,
            file_path,
            job_id,
            db,
            current_user
        )
        
        # Return job ID for status tracking
        return {
            "job_id": job_id,
            "message": "Upload job created successfully. Use the job_id to check processing status.",
            "status_endpoint": f"/v1/upload-jobs/{job_id}"
        }
        
    except Exception as e:
        # Clean up file if job creation failed
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create upload job: {str(e)}"
        )

@router.get("/v1/excel-template", tags=["Bulk Upload"])
async def download_question_excel_template(
    current_user: User = Depends(get_current_user)  
):
    """
    Download the Excel template for bulk question upload.

    This endpoint provides the standardized Excel template that must be used for bulk
    question uploads. The template includes all required columns, proper formatting,
    sample data, and detailed instructions.

    ## Template Features

    ### Column Structure:
    - **Question Data**: Question_text, answer_option_A/B/C/D, correct_answer
    - **Categorization**: chapter_name, topic_name, subtopic_name
    - **Classification**: Board, State, Medium, Class, Subject
    - **Metadata**: cognitive_learning, difficulty

    ### Sample Data:
    The template includes sample rows demonstrating:
    - Proper data formatting
    - Required field completion
    - Valid option values for dropdown fields
    - Correct answer format (A, B, C, or D)

    ### Instructions Sheet:
    - Detailed field descriptions
    - Valid values for each column
    - Data entry guidelines
    - Common error prevention tips

    ## Template Updates

    This template supports the enhanced bulk upload system with:
    - **Hierarchical Organization**: Board → State → Subject → Chapter → Topic → Subtopic
    - **Automatic Code Generation**: System generates all ID codes automatically
    - **Master Data Integration**: Automatic lookup and creation of reference data
    - **Enhanced Validation**: Comprehensive error checking and reporting

    ## Usage Guidelines

    1. **Download Template**: Use this endpoint to get the latest template
    2. **Fill Data**: Complete all required columns with your question data
    3. **Validate Data**: Ensure all required fields are filled
    4. **Upload File**: Use POST /v1/upload-excel to submit the completed template
    5. **Track Progress**: Monitor upload status using the job tracking endpoint

    ## Field Requirements

    ### Required Fields:
    - Question_text, answer_option_A/B/C/D, correct_answer
    - chapter_name, topic_name, subtopic_name
    - Medium, Board, State, Class, Subject
    - cognitive_learning, difficulty

    ### Auto-Created Fields:
    - Board, State, Medium (created if not found)
    - Chapter, Topic, Subtopic codes (generated automatically)
    - Question IDs and Taxonomy codes (generated automatically)

    ### Lookup Fields:
    - Subject (must exist in database)
    - cognitive_learning (Understanding, Information)
    - difficulty (Easy, Medium, Hard)

    ## Response Format

    Returns an Excel file (.xlsx) with:
    - Properly formatted column headers
    - Sample data rows
    - Data validation rules
    - Instructions worksheet

    **Authentication Required**: Valid JWT token
    **File Format**: Excel (.xlsx)
    **File Size**: Approximately 15-20KB
    """
    return generate_excel_template()


@router.get("/v1/upload-jobs/{job_id}", response_model=JobStatusResponseSchema, tags=["Bulk Upload"])
@require_permission("question_bank.upload")
async def get_upload_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the status and progress of an upload job.
    
    This endpoint provides real-time status tracking for bulk upload jobs, allowing
    users to monitor progress, view completion details, and retrieve error information
    for their upload operations.

    ## Job Status Tracking

    ### Status Values:
    - **`pending`**: Job created but not yet started processing
    - **`processing`**: Job is currently being processed
    - **`completed`**: Job finished successfully (may have some row errors)
    - **`failed`**: Job failed due to system error

    ### Progress Metrics:
    - **`total_rows`**: Total number of data rows in the Excel file
    - **`processed_rows`**: Number of rows processed so far
    - **`success_count`**: Number of rows successfully processed and saved
    - **`error_count`**: Number of rows that had validation or processing errors

    ### User Information:
    - **`uploadedby`**: Username of the user who initiated the upload job

    ## Response Examples

    ### Job in Progress:
    ```json
    {
      "job_id": "123e4567-e89b-12d3-a456-426614174000",
      "filename": "questions_batch_1.xlsx",
      "status": "processing",
      "uploadedby": "john_doe",
      "total_rows": 100,
      "processed_rows": 75,
      "success_count": 70,
      "error_count": 5,
      "error_details": null,
      "result_message": null,
      "result_loc": null,
      "started_at": "2025-09-10T06:30:00Z",
      "completed_at": null,
      "created_at": "2025-09-10T06:29:45Z"
    }
    ```

    ### Completed Job with Errors:
    ```json
    {
      "job_id": "123e4567-e89b-12d3-a456-426614174000",
      "filename": "questions_batch_1.xlsx",
      "status": "completed",
      "uploadedby": "john_doe",
      "total_rows": 100,
      "processed_rows": 100,
      "success_count": 95,
      "error_count": 5,
      "error_details": {
        "errors": [
          {
            "row_number": 3,
            "error_type": "missing_required_field",
            "error_message": "Missing required fields: Subject, Medium",
            "row_data": {
              "Question_text": "What is photosynthesis?",
              "Subject": "",
              "Medium": ""
            }
          },
          {
            "row_number": 15,
            "error_type": "lookup_failed",
            "error_message": "Subject 'Advanced Physics' not found in database",
            "row_data": {
              "Subject": "Advanced Physics"
            }
          }
        ],
        "error_summary": [
          {
            "error_type": "missing_required_field",
            "count": 3,
            "sample_message": "Missing required fields: Subject, Medium"
          },
          {
            "error_type": "lookup_failed",
            "count": 2,
            "sample_message": "Subject not found in database"
          }
        ]
      },
      "result_message": "Upload completed: 95 questions created successfully, 5 rows had errors",
      "result_loc": "https://bucket.s3.region.amazonaws.com/upload-results/2025/09/10/123e4567/result.xlsx",
      "started_at": "2025-09-10T06:30:00Z",
      "completed_at": "2025-09-10T06:32:30Z",
      "created_at": "2025-09-10T06:29:45Z"
    }
    ```

    ### Failed Job:
    ```json
    {
      "job_id": "123e4567-e89b-12d3-a456-426614174000",
      "filename": "invalid_file.xlsx",
      "status": "failed",
      "uploadedby": "john_doe",
      "total_rows": null,
      "processed_rows": 0,
      "success_count": 0,
      "error_count": 0,
      "error_details": null,
      "result_message": "File processing failed: Invalid Excel format or corrupted file",
      "result_loc": null,
      "started_at": "2025-09-10T06:30:00Z",
      "completed_at": "2025-09-10T06:30:15Z",
      "created_at": "2025-09-10T06:29:45Z"
    }
    ```
    """
    # Get job with user validation to ensure organizational context filtering
    upload_job = await JobService.get_job_with_user_validation(
        job_id=job_id,
        user_id=current_user.id,
        db=db
    )
    
    if not upload_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload job not found or you don't have permission to access it"
        )
    
    # Convert the job status to response schema
    return JobStatusResponseSchema(
        job_id=upload_job.id,
        filename=upload_job.filename,
        status=upload_job.status.value,
        uploadedby=upload_job.user.username,
        total_rows=upload_job.total_rows,
        processed_rows=upload_job.processed_rows,
        success_count=upload_job.success_count,
        error_count=upload_job.error_count,
        error_details=upload_job.error_details,
        result_message=upload_job.result_message,
        result_loc=upload_job.result_loc,
        started_at=upload_job.started_at,
        completed_at=upload_job.completed_at,
        created_at=upload_job.created_at
    )


@router.get("/v1/jobs", response_model=JobListResponseSchema, tags=["Bulk Upload"])
@require_permission("question_bank.upload")
async def list_all_upload_jobs(
    filename: Optional[str] = Query(None, description="Partial search by filename"),
    status: Optional[str] = Query(None, description="Filter jobs by status (pending, processing, completed, failed)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a list of upload jobs with optional filtering by filename and status.

    ## Query Parameters
    - **filename** (optional): Partial match on the uploaded file’s name
    - **status** (optional): Filter jobs by status. Valid values: `pending`, `processing`, `completed`, `failed`.

    ## Response
    Returns a list of jobs with complete details and total count.

    ## Response Example
    ```json
    {
      "jobs": [
        {
          "job_id": "2b7dca2d-aa1e-417b-92cc-1ef36d25855c",
          "filename": "questions_batch_1.xlsx",
          "status": "completed",
          "uploadedby": "john_doe",
          "total_rows": 100,
          "processed_rows": 100,
          "success_count": 95,
          "error_count": 5,
          "error_details": {
            "errors": [
              {
                "row_number": 3,
                "error_type": "missing_required_field",
                "error_message": "Missing required fields: Subject, Medium"
              }
            ],
            "error_summary": [
              {
                "error_type": "missing_required_field",
                "count": 1,
                "sample_message": "Missing required fields: Subject, Medium"
              }
            ]
          },
          "result_message": "Upload completed: 95 questions created successfully",
          "result_loc": "https://bucket.s3.region.amazonaws.com/upload-results/2025/09/10/2b7dca2d/result.xlsx",
          "started_at": "2025-09-10T06:09:05.961725Z",
          "completed_at": "2025-09-10T06:09:06.686458Z",
          "created_at": "2025-09-10T06:09:05.750222Z"
        }
      ],
      "total_count": 1
    }
    ```
    """
    # Validate status parameter if provided
    if status and status not in ['pending', 'processing', 'completed', 'failed']:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be one of: pending, processing, completed, failed"
        )

    # Query jobs from service layer with filename filter
    if status:
        all_jobs = await JobService.get_jobs_by_status(status, db, filename=filename)
    else:
        all_jobs = await JobService.get_all_jobs(db, filename=filename)

    # Convert DB objects → response schema
    job_responses = [
        JobStatusResponseSchema(
            job_id=job.id,
            filename=job.filename,
            status=job.status.value,
            uploadedby=job.user.username,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            success_count=job.success_count,
            error_count=job.error_count,
            error_details=job.error_details,
            result_message=job.result_message,
            result_loc=job.result_loc,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at
        )
        for job in all_jobs
    ]

    return JobListResponseSchema(
        jobs=job_responses,
        total_count=len(job_responses),
        grandTotal=len(job_responses)
    )
