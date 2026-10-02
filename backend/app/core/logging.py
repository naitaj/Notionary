import logging
import sys
import structlog
from contextvars import ContextVar
from typing import Optional

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
project_id_ctx: ContextVar[Optional[str]] = ContextVar("project_id", default=None)
job_id_ctx: ContextVar[Optional[str]] = ContextVar("job_id", default=None)

def add_context_vars(_, __, event_dict):
    req_id = request_id_ctx.get()
    if req_id:
        event_dict["request_id"] = req_id
    proj_id = project_id_ctx.get()
    if proj_id:
        event_dict["project_id"] = proj_id
    j_id = job_id_ctx.get()
    if j_id:
        event_dict["job_id"] = j_id
    return event_dict

def setup_logging(debug: bool = True):
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_context_vars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if debug:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug else logging.INFO),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger("notionary")
