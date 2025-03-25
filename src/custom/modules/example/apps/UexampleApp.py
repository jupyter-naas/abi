from fastapi import FastAPI, APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class UexampleResponse(BaseModel):
    """Response model for the Uexample app."""
    results: List[Dict[str, Any]] = Field(default_factory=list)
    message: str = Field("Success")

def create_example_app() -> FastAPI:
    """Creates a FastAPI app for the Uexample module."""
    app = FastAPI(
        title="Uexample App",
        description="API for the Uexample module",
        version="0.1.0"
    )
    
    router = APIRouter(prefix="/example", tags=["example"])
    
    @router.get("/", response_model=UexampleResponse)
    async def root():
        """Root endpoint for the Uexample app."""
        return UexampleResponse(
            results=[{"status": "ok"}],
            message="Uexample App is running"
        )
    
    @router.get("/status", response_model=UexampleResponse)
    async def status():
        """Status endpoint for the Uexample app."""
        return UexampleResponse(
            results=[{"status": "operational"}],
            message="Uexample services are operational"
        )
    
    # Add more endpoints as needed
    
    app.include_router(router)
    return app

# For direct execution
if __name__ == "__main__":
    import uvicorn
    app = create_example_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)

