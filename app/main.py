from fastapi import FastAPI

from app.routers.dataset import router

app = FastAPI(
    title="Insight AI",
    description="An AI-powered platform for data analysis and insights.",
    version="1.0.0",
)


@app.get("/")
def home():
    return {"message": "Insights AI backend is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/version")
def version():
    return {"version": "1.0.0"}


app.include_router(router)
