from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.organization import School
from app.decorators.permissions import require_permission
from app.services.s3_service import s3_service
from app.middleware.rbac import rbac_middleware

router = APIRouter()

@router.post("/v1/schools/images", tags=["Schools"], status_code=status.HTTP_201_CREATED)
@require_permission("school.update")
async def upload_school_images(
    udise_code: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    image: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload school images (logo and additional images) to S3 and store URLs in database.
    
    This endpoint accepts multipart form data to upload school images. Images are stored
    in S3 bucket and the URLs are saved to the school record in the database.
    
    ### Request Headers:
    - `Content-Type`: multipart/form-data
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - None
    
    ### Form Data Parameters:
    - **udise_code** (str, required): UDISE+ code of the school
    - **logo** (File, optional): School logo image file (field name MUST be 'logo')
    - **image** (File[], optional): Additional school images (0..n files, field name MUST be 'image')
    
    ### File Requirements:
    - **Content-Type**: Must be image/* (image/jpeg, image/png, etc.)
    - **File Size**: No explicit limit (S3 service limits apply)
    - **File Name**: Original filename will be preserved in S3 storage
    
    ### S3 Storage:
    - **Bucket**: smartqp-demo (configurable via S3_BUCKET_NAME env var)
    - **Region**: ap-south-1 (configurable via AWS_DEFAULT_REGION env var)
    - **Storage Path**: school_images/{udise_code}/{original-filename}
    
    ### Database Storage:
    - **Logo**: URL stored in `schools.logo_image_url` column
    - **Other Images**: URLs stored in `schools.other_images_urls` JSON array
    
    ### Response (application/json):
    - **201 Created**: Images uploaded successfully
    
    #### Example Response:
    ```json
    {
        "udise_code": "12345678901",
        "count": 3,
        "uploaded": [
            {
                "field": "logo",
                "filename": "school_logo.png",
                "s3_key": "school_images/12345678901/school_logo.png",
                "s3_url": "https://smartqp-demo.s3.ap-south-1.amazonaws.com/school_images/12345678901/school_logo.png",
                "content_type": "image/png"
            },
            {
                "field": "image",
                "filename": "building.jpg",
                "s3_key": "school_images/12345678901/building.jpg",
                "s3_url": "https://smartqp-demo.s3.ap-south-1.amazonaws.com/school_images/12345678901/building.jpg",
                "content_type": "image/jpeg"
            },
            {
                "field": "image",
                "filename": "playground.jpg",
                "s3_key": "school_images/12345678901/playground.jpg",
                "s3_url": "https://smartqp-demo.s3.ap-south-1.amazonaws.com/school_images/12345678901/playground.jpg",
                "content_type": "image/jpeg"
            }
        ]
    }
    ```
    
    ### Error Responses:
    - **400 Bad Request**: 
        ```json
        { "detail": "udise_code is required" }
        ```
    - **403 Forbidden**: 
        ```json
        { "detail": "Insufficient permissions or scope violation" }
        ```
    - **404 Not Found**: 
        ```json
        { "detail": "School with UDISE+ code '12345678901' not found" }
        ```
    - **415 Unsupported Media Type**: 
        ```json
        { "detail": "logo must be image/*" }
        ```
        ```json
        { "detail": "building.txt is not image/*" }
        ```
    - **500 Internal Server Error**: 
        ```json
        { "detail": "Failed to upload file to S3: AccessDenied" }
        ```
    
    ### RBAC Requirements:
    - **Permission**: `school.update`
    - **Scope**: User must have access to the school's organizational hierarchy
        - Super Admin: Can upload images for any school
        - VidyaShakthi Admin: Can upload images for schools in their organization
        - Block Admin: Can upload images for schools in their block
        - Teachers: Can upload images for their own school only
    
    ### Notes:
    - If a logo already exists, it will be replaced with the new logo
    - Additional images are appended to existing images (not replaced)
    - File names are sanitized to remove path separators
    - Images are validated to ensure they have image/* content type
    - S3 upload failures will return 500 error with specific error code
    - Database is updated only after successful S3 upload
    - All operations are performed within a database transaction
    
    ### Example cURL Request:
    ```bash
    curl -X POST "https://api.example.com/v1/schools/images" \
         -H "Authorization: Bearer your_jwt_token" \
         -F "udise_code=12345678901" \
         -F "logo=@school_logo.png" \
         -F "image=@building.jpg" \
         -F "image=@playground.jpg"
    ```
    """

    # --- 1) Validate school by UDISE+ code ---
    norm = (udise_code or "").strip()
    if not norm:
        raise HTTPException(status_code=400, detail="udise_code is required")

    result = await db.execute(select(School).where(School.udise_code == norm))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail=f"School with UDISE+ code '{norm}' not found")

    # --- 1b) Enforce hierarchical scope BEFORE any upload (RBAC) ---
    await rbac_middleware.validate_hierarchical_scope(
        db=db,
        user=current_user,
        target_organization_id=school.organization_id,
        target_block_id=school.block_id,
        target_school_id=school.id,
    )

    # --- 2) Validate content-types are images ---
    def _is_image(f: UploadFile) -> bool:
        return (f.content_type or "").startswith("image/")

    if logo and not _is_image(logo):
        raise HTTPException(status_code=415, detail="logo must be image/*")
    if image:
        for f in image:
            if not _is_image(f):
                raise HTTPException(status_code=415, detail=f"{f.filename} is not image/*")

    # --- 3) Upload helper using existing s3_service ---
    async def _upload_one(file: UploadFile, field: str) -> dict:
        filename = (file.filename or "unnamed").split("/")[-1].split("\\")[-1]
        key = f"school_images/{norm}/{filename}"
        content = await file.read()
        url = s3_service.upload_file_from_memory(
            content,
            key,
            file.content_type or "application/octet-stream",
        )
        return {"field": field, "filename": filename, "s3_key": key, "s3_url": url, "content_type": file.content_type}

    uploaded = []
    
    # Upload and save URLs to database
    if logo:
        logo_data = await _upload_one(logo, "logo")
        uploaded.append(logo_data)
        school.logo_image_url = logo_data["s3_url"]
    
    if image:
        other_urls = []
        for f in image:
            img_data = await _upload_one(f, "image")
            uploaded.append(img_data)
            other_urls.append(img_data["s3_url"])
        
        # Append to existing other images or create new list
        existing_urls = school.other_images_urls or []
        school.other_images_urls = existing_urls + other_urls
    
    # Commit changes to database
    await db.commit()
    await db.refresh(school)

    return {"udise_code": norm, "count": len(uploaded), "uploaded": uploaded}