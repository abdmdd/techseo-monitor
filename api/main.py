from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.routes import router

from config.settings import (
    APP_NAME,
    APP_VERSION
)


# ==================================================
# APP
# ==================================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API for TechSEO Monitor technical SEO audits."
)

# ==================================================
# ROUTES
# ==================================================

app.include_router(router)


# ==================================================
# ERROR HANDLERS
# ==================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "success" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "http_error",
            "message": str(exc.detail)
        }
    )


# ==================================================
# ROOT
# ==================================================

@app.get("/", summary="API root")

def root():

    return {
        "message": "TechSEO Monitor API"
    }
