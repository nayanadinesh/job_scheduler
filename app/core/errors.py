from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str):
        super().__init__("NOT_FOUND", f"{resource} not found", 404)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__("CONFLICT", message, 409)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__("UNAUTHORIZED", message, 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied"):
        super().__init__("FORBIDDEN", message, 403)


def error_response(code: str, message: str, status_code: int, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": code, "message": message, **({"details": details} if details else {})},
            "meta": {},
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.code, exc.message, exc.status_code)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logging.getLogger("app").exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response("INTERNAL_ERROR", "An unexpected error occurred", 500)
