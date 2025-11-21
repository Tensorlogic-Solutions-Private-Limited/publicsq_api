import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.api.v1.dependencies import api_auth_router
from app.api.v1.routes import api_router
from app.api.v2.routes import api_router_v2
from app.database import engine, Base
from app.middleware.error_handler import RBACErrorHandlerMiddleware, GlobalExceptionHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="SmartQP API", version="1.0.0")

# Add RBAC error handling middleware
app.add_middleware(RBACErrorHandlerMiddleware)

# Setup global exception handlers
GlobalExceptionHandler.setup_exception_handlers(app)

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(api_auth_router)
app.include_router(api_router)
app.include_router(api_router_v2)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns basic system status and database connectivity.
    """
    try:
        # Test database connection
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0",
            "database": "connected",
            "services": {
                "api": "running",
                "database": "connected",
                "upload_service": "available"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0",
            "database": "disconnected",
            "error": str(e),
            "services": {
                "api": "running",
                "database": "error",
                "upload_service": "unknown"
            }
        }

# To list all registered endpoints
@app.get("/list-endpoints", tags=["Debug"])
def list_endpoints():
    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoints.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name
            })
    return {"endpoints": endpoints}

# Add JWT bearer auth to Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # API description with bulk upload workflow
    api_description = """
## SmartQP API Documentation

### Bulk Upload System

Bulk upload system for question management with asynchronous processing capabilities.

#### Key Features:
- **Asynchronous Processing**: Upload files and track progress with job IDs
- **Enhanced Template Structure**: Support for Board, State, Subtopic categorization
- **Automatic Code Generation**: System generates question IDs, chapter codes, topic codes, and subtopic codes
- **Master Data Management**: Automatic creation of Board, State, and Medium entries
- **Comprehensive Error Handling**: Row-level error tracking with detailed reporting
- **Organizational Context**: Questions are automatically associated with user's organization

#### Bulk Upload Workflow:

1. **Download Template**: GET `/v1/excel-template` to get the standardized Excel template
2. **Prepare Data**: Fill the template with question data following the required format
3. **Upload File**: POST `/v1/upload-excel` to initiate async processing and receive job_id
4. **Monitor Progress**: GET `/v1/upload-jobs/{job_id}` to track processing status and progress
5. **Review Results**: Check final status for success/error counts and detailed error information

#### Template Structure:

**Required Columns:**
- `Question_text`: The question content
- `answer_option_A/B/C/D`: Answer choices
- `correct_answer`: Correct answer (A, B, C, or D)
- `chapter_name`, `topic_name`, `subtopic_name`: Hierarchical organization
- `Medium`, `Board`, `State`, `Class`, `Subject`: Classification fields
- `cognitive_learning`: Learning type (Understanding, Information)
- `difficulty`: Question difficulty (Easy, Medium, Hard)

#### Authentication:
All endpoints require JWT Bearer token authentication with appropriate permissions.

#### Error Handling:
The system provides comprehensive error handling with:
- Row-level error tracking
- Detailed error messages
- Error categorization (missing_required_field, lookup_failed, etc.)
- Partial success processing (valid rows are processed even if some fail)

For detailed examples and programming guides, see the complete API documentation.
    """
    
    openapi_schema = get_openapi(
        title="SmartQP API",
        version="1.0.0",
        description=api_description,
        routes=app.routes,
        servers=[
            {"url": "https://13.232.204.43", "description": "Production server (HTTPS)"},
            {"url": "http://13.232.204.43", "description": "Development server (HTTP)"}
        ]
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.openapi = custom_openapi