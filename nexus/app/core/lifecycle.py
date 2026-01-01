import asyncio
import logging
from typing import Callable, Awaitable
from fastapi import FastAPI
from app.api.dependencies import (
    get_mq_manager,
    get_settings,
    get_storage,
    get_state_manager,
    get_workflow_registry,
    get_orchestration_db,
)
from app.engine.orchestrator import WorkflowOrchestrator
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

def create_start_app_handler(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def start_app() -> None:
        try:
            settings = get_settings()
            # Ensure structured JSON logging is enabled early (so startup logs are consistent)
            setup_logging(settings.log_level)
            
            # Initialize services
            mq_manager = await get_mq_manager(settings)
            await mq_manager.connect()
            
            storage = await get_storage(settings)
            _db = await get_orchestration_db(settings)
            state_manager = get_state_manager(_db)
            
            # Ensure workflow registry loaded
            registry = get_workflow_registry(settings)
            
            orchestrator = WorkflowOrchestrator(mq_manager, state_manager, storage, registry)
            
            # Start consuming
            await mq_manager.start_consuming(
                queue_name=settings.event_queue,
                callback=orchestrator.handle_event
            )
            
            logger.info("Application startup complete")
        except Exception as e:
            logger.error(f"Startup failed: {e}")
            # We allow it to fail, but if running in uvicorn it might just log and continue or crash.
            # Ideally crash.
            raise e
        
    return start_app

def create_stop_app_handler(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def stop_app() -> None:
        try:
            settings = get_settings()
            logger.info("Application shutdown initiated")
            
            mq_manager = await get_mq_manager(settings)
            if mq_manager:
                await mq_manager.disconnect()
            # Best-effort dispose DB engine (optional)
            try:
                db = await get_orchestration_db(settings)
                db.engine.dispose()
            except Exception:
                pass
                
            logger.info("Application shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            
    return stop_app
