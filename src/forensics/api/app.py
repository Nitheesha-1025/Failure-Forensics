"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import Settings, load_settings
from ..db.session import create_db_engine, create_session_factory
from ..documents import DocumentService, LocalDocumentStorage
from ..llm_client import LLMClient
from ..pipeline import Pipeline
from ..pipeline_runs import PipelineRunService
from ..storage import TraceStore
from ..traces import TraceAccessService
from .analytics_routes import router as analytics_router
from .auth_routes import router as auth_router
from .document_routes import router as document_router
from .eval_routes import router as eval_router
from .pipeline_run_routes import router as pipeline_run_router
from .routes import router


@dataclass
class AppState:
    pipeline: Pipeline
    store: TraceStore
    judge_model: str


def create_app(state: AppState, *, settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        try:
            yield
        finally:
            await state.pipeline.client.aclose()
            if isinstance(state.pipeline.client, LLMClient):
                pass  # already closed above
            engine = getattr(app.state, "db_engine", None)
            if engine is not None:
                engine.dispose()

    app = FastAPI(
        title="failure-forensics",
        version="0.1.0",
        description="Multi-step AI pipeline observability with LLM-driven root-cause analysis.",
        lifespan=lifespan,
    )
    app.state.app_state = state
    app.state.settings = runtime_settings
    app.state.session_factory = None
    app.state.db_engine = None
    if runtime_settings.database_url:
        engine = create_db_engine(runtime_settings.database_url)
        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)

    app.state.document_service = None
    app.state.pipeline_run_service = None
    app.state.trace_access_service = None
    if runtime_settings.database_url:
        storage = LocalDocumentStorage(runtime_settings.upload_dir)
        document_service = DocumentService(storage, runtime_settings)
        app.state.document_service = document_service
        app.state.pipeline_run_service = PipelineRunService(document_service)
        app.state.trace_access_service = TraceAccessService()

    origins = [
        origin.strip()
        for origin in runtime_settings.cors_origins.split(",")
        if origin.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(document_router)
    app.include_router(pipeline_run_router)
    app.include_router(eval_router)
    app.include_router(analytics_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
