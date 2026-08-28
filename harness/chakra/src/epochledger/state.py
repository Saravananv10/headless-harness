"""Thread‑safe in‑memory storage for EpochLedger.
All collections are simple dicts keyed by UUID strings.
"""

import threading
from typing import Dict, List
from .models import Experiment, Run, Artifact, ApiCallEntry

_lock = threading.Lock()

# In‑memory stores
_experiments: Dict[str, Experiment] = {}
_runs: Dict[str, Run] = {}
_artifacts: Dict[str, Artifact] = {}
_api_calls: List[ApiCallEntry] = []  # ring buffer limited to last 100 entries

# Helper functions -----------------------------------------------------

def add_experiment(exp: Experiment) -> Experiment:
    with _lock:
        _experiments[exp.id] = exp
    return exp

def get_experiment(exp_id: str) -> Experiment:
    with _lock:
        return _experiments.get(exp_id)

def list_experiments() -> List[Experiment]:
    with _lock:
        return list(_experiments.values())

def add_run(run: Run) -> Run:
    with _lock:
        _runs[run.id] = run
    return run

def get_run(run_id: str) -> Run:
    with _lock:
        return _runs.get(run_id)

def list_runs(experiment_id: str) -> List[Run]:
    with _lock:
        return [r for r in _runs.values() if r.experiment_id == experiment_id]

def add_artifact(artifact: Artifact) -> Artifact:
    with _lock:
        _artifacts[artifact.id] = artifact
    return artifact

def get_artifact(artifact_id: str) -> Artifact:
    with _lock:
        return _artifacts.get(artifact_id)

def log_api_call(entry: ApiCallEntry) -> None:
    with _lock:
        _api_calls.append(entry)
        if len(_api_calls) > 100:
            _api_calls.pop(0)

def get_api_calls() -> List[ApiCallEntry]:
    with _lock:
        return list(_api_calls)
