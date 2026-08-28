"""Pydantic data models for EpochLedger.
All entities are stored in‑memory; IDs are UUID strings.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator

def _generate_id() -> str:
    return str(uuid.uuid4())

class ApiCallEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    method: str
    path: str
    status: int
    latency_ms: int

class Artifact(BaseModel):
    id: str = Field(default_factory=_generate_id)
    run_id: str
    name: str
    content_type: str
    bytes: bytes
    created_at: datetime = Field(default_factory=datetime.utcnow)

class GatePolicy(BaseModel):
    primary_metric: str
    min_delta_pct: float = Field(..., ge=0)
    guard_metric: Optional[str] = None
    guard_max_regress_pct: Optional[float] = None

class Run(BaseModel):
    id: str = Field(default_factory=_generate_id)
    experiment_id: str
    name: str
    status: str = Field(..., regex=r"^(RUNNING|FINISHED|FAILED)$")
    tags: List[str] = []
    params: Dict[str, Any] = {}
    metrics: Dict[str, List[Dict[str, Any]]] = {}
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    @validator("metrics", each_item=True)
    def check_metric_points(cls, v):
        # each metric is a list of {step, value}
        for point in v:
            if not isinstance(point, dict) or "step" not in point or "value" not in point:
                raise ValueError("Metric points must be dicts with 'step' and 'value'")
        return v

class Experiment(BaseModel):
    id: str = Field(default_factory=_generate_id)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    champion_run_id: Optional[str] = None
    gate_policy: Optional[GatePolicy] = None

# Request/response schemas for the API
class ExperimentCreate(BaseModel):
    name: str
    gate_policy: Optional[GatePolicy] = None

class ExperimentResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    champion_run_id: Optional[str] = None
    gate_policy: Optional[GatePolicy] = None
