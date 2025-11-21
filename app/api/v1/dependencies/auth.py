from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Union
from app.database import get_db
from app.models import master, user
from app.schemas.auth import (LoginRequest, LoginResponse, RoleListResponse)
from app.utils import auth
from sqlalchemy.orm import joinedload
from app.utils.get_user_role import get_user_role
from app.utils.auth import get_current_user
from app.decorators.permissions import require_permission
from app.middleware.rbac import rbac_middleware

router = APIRouter()

@router.post("/v1/login", tags=["Authentication"], response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
        Authenticate a user and return a JWT access token with organizational context.

        ### Request Headers:
        - `Content-Type`: application/json

        ### Path Parameters:
        - None

        ### Query Parameters:
        - None

        ### Request Body (application/json):
        - **username** (str): The user's username.
        - **password** (str): The user's password.

        #### Example:
        ```json
        {
            "username": "john_doe",
            "password": "strongPassword123"
        }
        ```

        ### Response (application/json):
        - **200 OK**: Successful authentication returns a JWT token with organizational context.
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "username":"john_doe",
            "user_id": 10,
            "role_name": "Teacher",
            "role_code": "teacher"
        }
        ```

        ### Error Responses:
        - **400 Bad Request**
            - Invalid credentials:
            ```json
            {
                "detail": "Invalid username or password"
            }
            ```

        ### Notes:
        - The returned JWT token should be included in the `Authorization` header for protected routes in this format:
        ```
        Authorization: Bearer <access_token>
        ```
        - The token includes the following claims in its payload:
            - **sub**: The username
            - **role**: The user's role code
            - **org_id**: Organization ID (if applicable)
            - **block_id**: Block ID (if applicable)
            - **school_id**: School ID (if applicable)
    """
    result = await db.execute(
        select(user.User)
        .filter(
            user.User.username == request.username,
            user.User.is_active == True
        )
        .options(
            joinedload(user.User.role),
            joinedload(user.User.organization),
            joinedload(user.User.block),
            joinedload(user.User.school)
        )
    )
    user_record = result.unique().scalar_one_or_none()

    if not user_record or not auth.verify_password(request.password, user_record.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    # Include organizational context in token
    token_data = {
        "sub": user_record.username,
        "role": user_record.role.role_code,
        "user_id": user_record.id
    }
    
    if user_record.organization_id:
        token_data["org_id"] = user_record.organization_id
    if user_record.block_id:
        token_data["block_id"] = user_record.block_id
    if user_record.school_id:
        token_data["school_id"] = user_record.school_id

    access_token = auth.create_access_token(data=token_data)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_uuid=user_record.uuid,
        username=user_record.username,
        role_name=user_record.role.role_name,
        role_code=user_record.role.role_code
    )

@router.get("/v1/roles", response_model=RoleListResponse, tags=["Authentication"])
async def get_roles(db: AsyncSession = Depends(get_db)):
    """
    Retrieve all available user roles.

    ### Request Headers:
    - `Content-Type`: application/json
    - *(Optional)* `Authorization`: Bearer token (if roles are protected)

    ### Path Parameters:
    - None

    ### Query Parameters:
    - None

    ### Request Body:
    - None (GET request does not require a body)

    ### Response (application/json):
    - **200 OK**: List of available roles

    #### Response Schema:
    ```json
    {
    "data": [
        {
            "role_code": "100",
            "role_name": "admin"
        },
        {
            "role_code": "101",
            "role_name": "educator"
        }
            ]
    }
    ```

    ### Error Responses:
    - **500 Internal Server Error**: If there is a database or server issue

    ### Notes:
    - This endpoint can be used to populate dropdowns or options for user role selection during registration.
    - You can expand this in the future to include role descriptions or permissions if needed.
    """
    result = await db.execute(select(user.Role))
    roles = result.scalars().all()
    return RoleListResponse(data=roles)



