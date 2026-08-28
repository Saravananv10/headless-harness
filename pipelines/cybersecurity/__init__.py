"""Cybersecurity Pipeline module package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cybersecurity_pipeline.data_generator import generate_all as generate_cyber_data
    from cybersecurity_pipeline.prompts import build_cyber_pipeline_objective


def __getattr__(name: str):
    if name == "generate_cyber_data":
        from cybersecurity_pipeline.data_generator import generate_all
        return generate_all
    if name == "build_cyber_pipeline_objective":
        from cybersecurity_pipeline.prompts import build_cyber_pipeline_objective
        return build_cyber_pipeline_objective
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "generate_cyber_data",
    "build_cyber_pipeline_objective",
]
