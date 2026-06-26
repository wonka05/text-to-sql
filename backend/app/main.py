from fastapi import FastAPI
from app.api.employee import router as employee_router
from app.api.query import router as query_router

app = FastAPI(
    title="QueryGenie",
    version="1.0.0"
)

app.include_router(employee_router)
app.include_router(query_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to QueryGenie 🚀"
    }