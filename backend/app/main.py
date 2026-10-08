from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.query import router as query_router
from app.core.config import settings

app = FastAPI(
    title="QueryGenie",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(query_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to QueryGenie"
    }
