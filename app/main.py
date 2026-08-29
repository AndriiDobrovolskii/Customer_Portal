from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.db.session import create_engine_and_sessionmaker
from app.modules.users.exceptions import DuplicateEmailError, RegistrationValidationError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    yield
    await engine.dispose()


app = FastAPI(title="Customer Portal", lifespan=lifespan)
app.include_router(api_v1_router)

# Local-only allowance for the gitignored dev-gui/ test page, served via
# `python -m http.server 5500 --directory dev-gui`. Not a public API concern.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Location"],
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


@app.exception_handler(DuplicateEmailError)
async def duplicate_email_error_handler(request: Request, exc: DuplicateEmailError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Email is already registered."})


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # FastAPI's default handler echoes exc.errors() verbatim, which includes the
    # rejected `input` value — that would leak a submitted password (FR-6 applies
    # to every registration attempt, not just the ones handled by our own domain
    # exceptions). Keep only the non-sensitive fields.
    sanitized = [
        {"type": error["type"], "loc": error["loc"], "msg": error["msg"]} for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": sanitized})
