import logging
import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.ontology import router as ontology_router
from api.integrations import fec

# Suppress all RDFLib warnings
warnings.filterwarnings("ignore", category=UserWarning, module="rdflib")
logging.getLogger('rdflib').setLevel(logging.CRITICAL)

app = FastAPI(
    title="ABI",
    description="Organizational AI System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the ontology router without authentication
app.include_router(
    ontology_router,
    prefix="/ontology",
    tags=["Ontology"]
)

# Include FEC router
app.include_router(fec.router)

@app.get("/")
async def root():
    return {"message": "ABI Framework API"}