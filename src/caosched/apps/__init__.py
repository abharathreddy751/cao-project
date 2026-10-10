"""Application-level workflows: multi-stage DAGs whose tasks pass real data."""
from caosched.apps.image_pipeline import build_image_pipeline, run_reference, verify_output
from caosched.apps.stages import STAGES, run_stage

__all__ = ["STAGES", "build_image_pipeline", "run_reference", "run_stage", "verify_output"]
