from fastapi import APIRouter, HTTPException, UploadFile, File
from pathlib import Path
from typing import Dict, List
from integrations.fec import FECProcessor, FECConfig
import shutil

router = APIRouter(prefix="/fec", tags=["FEC"])

@router.post("/process")
async def process_fec_file(file: UploadFile = File(...)) -> Dict:
    """Process uploaded FEC file"""
    config = FECConfig()
    processor = FECProcessor(config)
    
    # Save uploaded file
    file_path = config.FEC_INPUT_PATH / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File upload failed: {str(e)}")
    
    # Process file
    try:
        processor.process_file(file_path)
        return {"message": "File processed successfully", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Processing failed: {str(e)}")

@router.get("/reports")
async def get_reports() -> List[Dict]:
    """Get list of generated FEC reports"""
    config = FECConfig()
    reports = []
    
    for file_path in config.FEC_OUTPUT_PATH.glob("*.parquet"):
        reports.append({
            "filename": file_path.name,
            "created": file_path.stat().st_mtime,
            "size": file_path.stat().st_size
        })
    
    return reports 