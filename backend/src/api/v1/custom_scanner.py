from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, random
from datetime import datetime

router = APIRouter(prefix="/api/v1/custom-scanner", tags=["custom-scanner"])

_scanners: dict[str, dict] = {}

class ScannerStep(BaseModel):
    id: str
    type: str  # http_request, dns_lookup, port_check, regex_extract, python_script
    config: dict
    output_key: str

class CustomScanner(BaseModel):
    id: str
    name: str
    description: str
    input_type: str  # ip, domain, email, url
    steps: list[ScannerStep]
    enabled: bool
    run_count: int
    last_run: Optional[str]
    created_at: str

class CreateScannerInput(BaseModel):
    name: str
    description: str
    input_type: str = "domain"

@router.get("/scanners", response_model=list[CustomScanner])
async def list_scanners():
    return [CustomScanner(**s) for s in _scanners.values()]

@router.post("/scanners", response_model=CustomScanner)
async def create_scanner(data: CreateScannerInput):
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    scanner = {
        "id": sid, "name": data.name, "description": data.description,
        "input_type": data.input_type, "steps": [], "enabled": True,
        "run_count": 0, "last_run": None, "created_at": now
    }
    _scanners[sid] = scanner
    return CustomScanner(**scanner)

@router.post("/scanners/{scanner_id}/steps", response_model=CustomScanner)
async def add_step(scanner_id: str, step_type: str, output_key: str, config: Optional[str] = None):
    if scanner_id not in _scanners:
        raise HTTPException(status_code=404, detail="Scanner not found")
    import json
    step = ScannerStep(
        id=str(uuid.uuid4()), type=step_type,
        config=json.loads(config) if config else {},
        output_key=output_key
    )
    _scanners[scanner_id]["steps"].append(step.model_dump())
    return CustomScanner(**_scanners[scanner_id])

@router.post("/scanners/{scanner_id}/run")
async def run_scanner(scanner_id: str, input_value: str):
    if scanner_id not in _scanners:
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner = _scanners[scanner_id]
    scanner["run_count"] += 1
    scanner["last_run"] = datetime.utcnow().isoformat()
    results = {}
    for step in scanner["steps"]:
        results[step["output_key"]] = f"mock_result_for_{step['type']}_{input_value}"
    return {"scanner_id": scanner_id, "input": input_value, "results": results, "status": "completed"}
