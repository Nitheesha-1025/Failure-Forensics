from __future__ import annotations


class PipelineRunError(Exception):
    pass


class PipelineRunNotFoundError(PipelineRunError):
    pass


class PipelineRunAlreadyInProgressError(PipelineRunError):
    """Document already has a pipeline run in progress."""
