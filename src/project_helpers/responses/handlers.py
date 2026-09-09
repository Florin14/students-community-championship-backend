import logging

from fastapi import Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError

from project_helpers.error import Error
from project_helpers.exceptions import ErrorException


def _error_body(error: Error, message=None, fields=None):
    return {
        "code": error.code,
        "message": message or error.message,
        "fields": fields or [],
    }


async def error_exception_handler(request: Request, exc: ErrorException):
    return JSONResponse(status_code=exc.status_code, content=exc.as_dict())


async def http_exception_handler(request: Request, exc: HTTPException):
    error = {
        status.HTTP_401_UNAUTHORIZED: Error.INVALID_TOKEN,
        status.HTTP_403_FORBIDDEN: Error.FORBIDDEN,
        status.HTTP_404_NOT_FOUND: Error.NOT_FOUND,
        status.HTTP_409_CONFLICT: Error.CONFLICT,
    }.get(exc.status_code, Error.BAD_REQUEST)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(error, message=str(exc.detail)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    fields = [
        f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', '')}"
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(Error.VALIDATION_ERROR, fields=fields),
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logging.exception("Database error: %s", exc)
    if isinstance(exc, (IntegrityError, DataError)):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(Error.DB_INSERT_ERROR),
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(Error.DB_ACCESS_ERROR),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(Error.UNKNOWN),
    )
