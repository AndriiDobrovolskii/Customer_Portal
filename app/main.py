from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.problem_details import ProblemError
from app.db.session import create_engine_and_sessionmaker
from app.modules.users.exceptions import DuplicateEmailError, RegistrationValidationError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.runtime_database_url)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    valkey_client: Redis = Redis.from_url(settings.valkey_url, decode_responses=True)
    app.state.valkey_client = valkey_client
    yield
    await engine.dispose()
    await valkey_client.aclose()


app = FastAPI(title="Customer Portal", lifespan=lifespan)
app.include_router(api_v1_router)

# Local-only allowance for the gitignored dev-gui/ test page, served via
# `python -m http.server 5500 --directory dev-gui`. Not a public API concern.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Location", "ETag"],
)


@app.exception_handler(RegistrationValidationError)
async def registration_validation_error_handler(
    request: Request, exc: RegistrationValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "errors": [
                {"field": error.field, "message": error.message, "code": error.code}
                for error in exc.errors
            ]
        },
    )


@app.exception_handler(ProblemError)
async def problem_error_handler(request: Request, exc: ProblemError) -> JSONResponse:
    content: dict[str, object] = {
        "type": f"https://portal.internal/errors/{exc.type_slug}",
        "title": exc.title,
        "status": exc.status,
        "detail": exc.detail,
        "instance": request.url.path,
    }
    if exc.errors is not None:
        content["errors"] = [
            {"field": error.field, "code": error.code, "message": error.message}
            for error in exc.errors
        ]
    return JSONResponse(
        status_code=exc.status,
        media_type="application/problem+json",
        headers=exc.headers,
        content=content,
    )


@app.exception_handler(DuplicateEmailError)
async def duplicate_email_error_handler(request: Request, exc: DuplicateEmailError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Email is already registered."})


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # FastAPI's default handler echoes exc.errors() verbatim, which includes
    # the rejected `input` value — that would leak a submitted password
    # (BR-004 applies to every validated request, not just registration).
    # Reshaped as this project's problem+json error array ({field, code,
    # message}), matching problem_error_handler's shape (FR-6/LI-AC6).
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "code": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    content: dict[str, object] = {
        "type": "https://portal.internal/errors/validation-failed",
        "title": "Validation Failed",
        "status": 422,
        "detail": "The request body failed validation.",
        "instance": request.url.path,
        "errors": errors,
    }
    return JSONResponse(status_code=422, media_type="application/problem+json", content=content)
