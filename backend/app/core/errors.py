from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class ProblemException(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        problem_type: str = "about:blank",
        instance: Optional[str] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.problem_type = problem_type
        self.instance = instance
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "type": self.problem_type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }
        if self.instance:
            data["instance"] = self.instance
        if self.errors:
            data["errors"] = self.errors
        return data

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException):
        instance = exc.instance or request.url.path
        body = exc.to_dict()
        body["instance"] = instance
        return JSONResponse(
            status_code=exc.status,
            content=body,
            headers={"Content-Type": "application/problem+json"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://notionary.dev/errors/validation-error",
                "title": "Validation Error",
                "status": 422,
                "detail": "Request body or query parameters failed validation.",
                "instance": request.url.path,
                "errors": exc.errors(),
            },
            headers={"Content-Type": "application/problem+json"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "about:blank",
                "title": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
                "status": exc.status_code,
                "detail": str(exc.detail),
                "instance": request.url.path,
            },
            headers={"Content-Type": "application/problem+json"},
        )
