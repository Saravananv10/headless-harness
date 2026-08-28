"""API router for EpochLedger experiment endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from .models import ExperimentCreate, ExperimentResponse
from .state import add_experiment, get_experiment, list_experiments

router = APIRouter()

@router.post("/api/experiments", response_model=ExperimentResponse)
async def create_experiment(payload: ExperimentCreate):
    try:
        # Convert request into full Experiment model (id generated automatically)
        exp = ExperimentResponse(**ExperimentCreate(**payload.dict()).dict())
        # Actually store using the full Experiment model
        from .models import Experiment
        exp_full = Experiment(name=payload.name, gate_policy=payload.gate_policy)
        add_experiment(exp_full)
        return ExperimentResponse(**exp_full.dict())
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
        )

@router.get("/api/experiments", response_model=list[ExperimentResponse])
async def list_all_experiments():
    exps = list_experiments()
    return [ExperimentResponse(**e.dict()) for e in exps]

@router.get("/api/experiments/{exp_id}", response_model=ExperimentResponse)
async def get_experiment_detail(exp_id: str):
    exp = get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": f"Experiment {exp_id} not found"}})
    return ExperimentResponse(**exp.dict())
