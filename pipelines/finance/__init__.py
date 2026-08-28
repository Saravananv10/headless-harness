"""Finance Pipeline module package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finance_pipeline.data_generator import generate_all as generate_finance_data
    from finance_pipeline.prompts import build_finance_pipeline_objective


def __getattr__(name: str):
    if name == "generate_finance_data":
        from finance_pipeline.data_generator import generate_all
        return generate_all
    if name == "build_finance_pipeline_objective":
        from finance_pipeline.prompts import build_finance_pipeline_objective
        return build_finance_pipeline_objective
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "generate_finance_data",
    "build_finance_pipeline_objective",
]
