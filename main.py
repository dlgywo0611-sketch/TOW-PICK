from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TOW-PICK API",
    description="HEART BRIDGE 백엔드 API",
)


@app.get("/")
def root():
    return {"message": "TOW-PICK API is running"}


@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite"}


@app.post("/messages", response_model=schemas.MessageRead)
def create_message(
    message: schemas.MessageCreate,
    db: Session = Depends(get_db),
):
    new_message = models.Message(content=message.content)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message


@app.get("/messages", response_model=list[schemas.MessageRead])
def read_messages(db: Session = Depends(get_db)):
    return db.query(models.Message).all()