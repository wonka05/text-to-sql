from fastapi import FastAPI
from app.api.employee import router as employee_router
from app.api.query import router as query_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="QueryGenie",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employee_router)
app.include_router(query_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to QueryGenie"
    }