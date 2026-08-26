from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.core.exceptions import DuplicateEmailError, RegistrationValidationError
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_engine(settings.database_url)
    yield
    await dispose_engine()


app = FastAPI(title="Customer Portal", lifespan=lifespan)
app.include_router(users_router)


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
