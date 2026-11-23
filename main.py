import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TOW-PICK API",
    description="HEART BRIDGE 백엔드 API",
)


def get_user_or_404(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def get_couple_with_members(
    db: Session,
    couple_id: int,
) -> models.Couple | None:
    return db.scalar(
        select(models.Couple)
        .options(selectinload(models.Couple.members))
        .where(models.Couple.id == couple_id)
    )


@app.get("/")
def root():
    return {"message": "TOW-PICK API is running"}


@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite"}


@app.post(
    "/users",
    response_model=schemas.UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(
        select(models.User).where(models.User.email == user.email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = models.User(
        email=user.email,
        nickname=user.nickname,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users", response_model=list[schemas.UserRead])
def read_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.User)).all())


@app.post(
    "/couples",
    response_model=schemas.CoupleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_couple(
    request: schemas.CoupleCreate,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, request.user_id)

    if user.couple_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to a couple",
        )

    while True:
        invite_code = secrets.token_hex(4).upper()
        existing_couple = db.scalar(
            select(models.Couple).where(
                models.Couple.invite_code == invite_code
            )
        )
        if existing_couple is None:
            break

    couple = models.Couple(invite_code=invite_code)
    db.add(couple)
    db.flush()

    user.couple_id = couple.id
    db.commit()

    created_couple = get_couple_with_members(db, couple.id)
    return created_couple


@app.post("/couples/join", response_model=schemas.CoupleRead)
def join_couple(
    request: schemas.CoupleJoin,
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, request.user_id)

    if user.couple_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to a couple",
        )

    couple = db.scalar(
        select(models.Couple)
        .options(selectinload(models.Couple.members))
        .where(
            models.Couple.invite_code
            == request.invite_code.upper()
        )
    )
    if couple is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found",
        )

    if len(couple.members) >= 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Couple already has two members",
        )

    user.couple_id = couple.id
    db.commit()

    joined_couple = get_couple_with_members(db, couple.id)
    return joined_couple


@app.get(
    "/couples/{couple_id}",
    response_model=schemas.CoupleRead,
)
def read_couple(
    couple_id: int,
    db: Session = Depends(get_db),
):
    couple = get_couple_with_members(db, couple_id)
    if couple is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Couple not found",
        )
    return couple


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
    return list(db.scalars(select(models.Message)).all())