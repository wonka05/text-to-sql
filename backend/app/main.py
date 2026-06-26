from fastapi import FastAPI

app = FastAPI(
    title="AI SQL Assistant",
    description="Convert natural language into SQL queries using AI",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Welcome to AI SQL Assistant 🚀"
    }


@app.get("/health")
def health():
    return {
        "status": "Healthy"
    }