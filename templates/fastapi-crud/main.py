from fastapi import FastAPI
from .database import engine
from .models import Base
from .routes import router

app = FastAPI(title="CRUD API", version="1.0.0")

Base.metadata.create_all(bind=engine)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "CRUD API is running"}
