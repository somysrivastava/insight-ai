from fastapi import FastAPI

import app.models
from app.database import Base, engine
from app.routers import dataset, auth
from app.routers.cleaning import router as cleaning_router

app = FastAPI(
    title="Insight AI",
    description="An AI-powered platform for data analysis and insights.",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)
# create_all() looks at all classes that inherit from Base
# and creates their tables in PostgreSQL if they don't already exist
# This runs every time the server starts — safe to run multiple times


@app.get("/")
def home():
    return {"message": "Insights AI backend is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/version")
def version():
    return {"version": "1.0.0"}


app.include_router(dataset.router)
app.include_router(auth.router)
app.include_router(cleaning_router)