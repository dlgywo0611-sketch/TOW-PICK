import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from database import Base, engine, get_db

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError

from auth import (
    create_access_token,
    decode_access_token,
    get_token_expiration,
    hash_password,
    hash_token,
    verify_password,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TOW-PICK API",
    description="HEART BRIDGE 백엔드 API",
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
        hashed_password=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(models.User).where(
            models.User.email == form_data.username
        )
    )

    if user is None or not verify_password(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return schemas.Token(
        access_token=create_access_token(str(user.id)),
        token_type="bearer",
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    revoked_token = db.scalar(
        select(models.RevokedToken).where(
            models.RevokedToken.token_hash == hash_token(token)
        )
    )

    if revoked_token is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(decode_access_token(token))
    except (InvalidTokenError, ValueError) as error:
        raise credentials_exception from error

    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_exception

    return user


@app.get("/users/me", response_model=schemas.UserRead)
def read_current_user(
    current_user: models.User = Depends(get_current_user),
):
    return current_user


@app.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    token_hash = hash_token(token)

    existing_token = db.scalar(
        select(models.RevokedToken).where(
            models.RevokedToken.token_hash == token_hash
        )
    )

    if existing_token is None:
        revoked_token = models.RevokedToken(
            token_hash=token_hash,
            expires_at=get_token_expiration(token),
        )
        db.add(revoked_token)
        db.commit()

    return {"message": "Successfully logged out"}


@app.post(
    "/couples",
    response_model=schemas.CoupleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_couple(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = current_user

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
    current_user: models.User = Depends(get_current_user),
):
    user = current_user

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
    "/couples/me",
    response_model=schemas.CoupleRead,
)
def read_my_couple(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to a couple",
        )

    couple = get_couple_with_members(
        db,
        current_user.couple_id,
    )

    if couple is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Couple not found",
        )

    return couple

@app.post(
    "/decisions",
    response_model=schemas.DecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    request: schemas.DecisionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = models.Decision(
        couple_id=current_user.couple_id,
        created_by_id=current_user.id,
        title=request.title,
        status="open",
    )

    db.add(decision)
    db.commit()
    db.refresh(decision)

    return decision

@app.post(
    "/decisions/{decision_id}/candidates",
    response_model=schemas.DecisionCandidateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_decision_candidate(
    decision_id: int,
    request: schemas.DecisionCandidateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    decision = db.get(models.Decision, decision_id)

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    if decision.couple_id != current_user.couple_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this decision",
        )

    if decision.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Decision is already closed",
        )

    current_candidate = db.scalar(
        select(models.DecisionCandidate)
        .where(
            models.DecisionCandidate.decision_id == decision_id,
            models.DecisionCandidate.is_current.is_(True),
        )
        .order_by(models.DecisionCandidate.version.desc())
    )

    next_version = 1

    if current_candidate is not None:
        current_candidate.is_current = False
        next_version = current_candidate.version + 1

    candidate = models.DecisionCandidate(
        decision_id=decision_id,
        content=request.content,
        version=next_version,
        is_current=True,
    )

    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return candidate

@app.post(
    "/candidates/{candidate_id}/approve",
    response_model=schemas.DecisionApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def approve_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    candidate = db.get(models.DecisionCandidate, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    decision = db.get(models.Decision, candidate.decision_id)

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    if decision.couple_id != current_user.couple_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this decision",
        )

    if decision.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Decision is already closed",
        )

    if not candidate.is_current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the current candidate can be approved",
        )

    existing_approval = db.scalar(
        select(models.DecisionApproval).where(
            models.DecisionApproval.candidate_id == candidate_id,
            models.DecisionApproval.user_id == current_user.id,
        )
    )

    if existing_approval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already approved this candidate",
        )

    approval = models.DecisionApproval(
        candidate_id=candidate_id,
        user_id=current_user.id,
        approved=True,
    )

    db.add(approval)
    db.flush()

    approvals = db.scalars(
        select(models.DecisionApproval).where(
            models.DecisionApproval.candidate_id == candidate_id,
            models.DecisionApproval.approved.is_(True),
        )
    ).all()

    couple = get_couple_with_members(
        db,
        decision.couple_id,
    )

    if (
        couple is not None
        and len(couple.members) == 2
        and len({item.user_id for item in approvals}) == 2
    ):
        decision.status = "confirmed"

    db.commit()
    db.refresh(approval)

    return approval

@app.post("/messages", response_model=schemas.MessageRead)
def create_message(
    message: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    new_message = models.Message(
        content=message.content,
        sender_id=current_user.id,
        couple_id=current_user.couple_id,
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return new_message


@app.get("/messages", response_model=list[schemas.MessageRead])
def read_messages(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    messages = db.scalars(
        select(models.Message)
        .where(
            models.Message.couple_id == current_user.couple_id
        )
        .order_by(models.Message.id)
    )
    return list(messages.all())