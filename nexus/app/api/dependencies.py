from functools import lru_cache
from typing import AsyncGenerator
from fastapi import Depends
from app.core.config import Settings, get_settings
from app.infrastructure.mq_manager import MQManager
from app.infrastructure.storage import StorageBackend, MinIOStorage, StateManager
from app.engine.workflows import WorkflowRegistry
from app.engine.orchestrator import WorkflowOrchestrator
from app.services.job_service import JobService
from app.services.status_service import StatusService
from app.services.report_service import ReportService

# Singletons
_mq_manager = None
_storage = None
_workflow_registry = None

async def get_mq_manager(settings: Settings = Depends(get_settings)) -> MQManager:
    global _mq_manager
    if not _mq_manager:
        _mq_manager = MQManager(settings)
    return _mq_manager

async def get_storage(settings: Settings = Depends(get_settings)) -> StorageBackend:
    global _storage
    if not _storage:
        _storage = MinIOStorage(settings)
    return _storage

def get_state_manager(storage: StorageBackend = Depends(get_storage)) -> StateManager:
    return StateManager(storage)

def get_workflow_registry(settings: Settings = Depends(get_settings)) -> WorkflowRegistry:
    global _workflow_registry
    if not _workflow_registry:
        # We catch error or allow it to propagate?
        # If file missing, it raises FileNotFoundError.
        # Ideally we want this to fail fast at startup, but here it's lazy.
        try:
            _workflow_registry = WorkflowRegistry.from_yaml(settings.workflow_config_path)
        except Exception as e:
            # Fallback for testing if file not exists?
            # Or just let it fail.
            # For now, we assume file will be created.
            raise e
    return _workflow_registry

def get_orchestrator(
    mq: MQManager = Depends(get_mq_manager),
    state_manager: StateManager = Depends(get_state_manager),
    storage: StorageBackend = Depends(get_storage),
    registry: WorkflowRegistry = Depends(get_workflow_registry)
) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(mq, state_manager, storage, registry)

def get_job_service(
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator)
) -> JobService:
    return JobService(orchestrator)

def get_status_service(
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator)
) -> StatusService:
    return StatusService(orchestrator)

def get_report_service(
    orchestrator: WorkflowOrchestrator = Depends(get_orchestrator)
) -> ReportService:
    return ReportService(orchestrator)
