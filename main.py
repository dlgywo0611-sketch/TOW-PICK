import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, aliased, selectinload

import models
import schemas
from database import Base, engine, get_db
from recommendation_engine import choose_balanced_option

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

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
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


def get_decision_for_current_couple(
    db: Session,
    decision_id: int,
    current_user: models.User,
) -> models.Decision:
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

    return decision


def build_decision_detail(
    db: Session,
    decision: models.Decision,
) -> schemas.DecisionDetailRead:
    current_candidate = db.scalar(
        select(models.DecisionCandidate)
        .where(
            models.DecisionCandidate.decision_id == decision.id,
            models.DecisionCandidate.is_current.is_(True),
        )
        .order_by(models.DecisionCandidate.version.desc())
    )

    candidate_status = None
    if current_candidate is not None:
        approved_user_ids = set(
            db.scalars(
                select(models.DecisionApproval.user_id).where(
                    models.DecisionApproval.candidate_id
                    == current_candidate.id,
                    models.DecisionApproval.approved.is_(True),
                )
            ).all()
        )
        couple = get_couple_with_members(db, decision.couple_id)
        members = [] if couple is None else couple.members

        candidate_status = schemas.DecisionCandidateStatusRead(
            id=current_candidate.id,
            decision_id=current_candidate.decision_id,
            content=current_candidate.content,
            version=current_candidate.version,
            is_current=current_candidate.is_current,
            approval_count=len(approved_user_ids),
            member_approvals=[
                schemas.DecisionMemberApprovalRead(
                    user_id=member.id,
                    approved=member.id in approved_user_ids,
                )
                for member in sorted(members, key=lambda item: item.id)
            ],
        )

    return schemas.DecisionDetailRead(
        id=decision.id,
        couple_id=decision.couple_id,
        created_by_id=decision.created_by_id,
        title=decision.title,
        status=decision.status,
        current_candidate=candidate_status,
        confirmed=decision.status == "confirmed",
    )


@app.get("/")
def root():
    return {"message": "TOW-PICK API is running"}


@app.get("/app", include_in_schema=False)
def web_app():
    return FileResponse(FRONTEND_DIR / "index.html")


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

    member = aliased(models.User)
    member_count = select(func.count(member.id)).where(
        member.couple_id == couple.id
    ).scalar_subquery()
    try:
        result = db.execute(
            update(models.User)
            .where(
                models.User.id == user.id,
                models.User.couple_id.is_(None),
                member_count < 2,
            )
            .values(couple_id=couple.id)
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Couple already has two members",
            )
        db.commit()
    except OperationalError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Couple join conflicted with another update",
        ) from error

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


@app.get(
    "/decisions",
    response_model=list[schemas.DecisionRead],
)
def read_decisions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decisions = db.scalars(
        select(models.Decision)
        .where(models.Decision.couple_id == current_user.couple_id)
        .order_by(models.Decision.id.desc())
    )
    return list(decisions.all())


@app.get(
    "/decisions/{decision_id}",
    response_model=schemas.DecisionDetailRead,
)
def read_decision(
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = get_decision_for_current_couple(
        db,
        decision_id,
        current_user,
    )
    return build_decision_detail(db, decision)


@app.put(
    "/decisions/{decision_id}/conditions/me",
    response_model=schemas.DecisionConditionRead,
)
def upsert_my_decision_condition(
    decision_id: int,
    request: schemas.DecisionConditionUpsert,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = get_decision_for_current_couple(
        db,
        decision_id,
        current_user,
    )

    if decision.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Decision is already closed",
        )

    candidate_id = db.scalar(
        select(models.DecisionCandidate.id).where(
            models.DecisionCandidate.decision_id == decision.id
        )
    )
    if candidate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conditions cannot be changed after candidate creation",
        )

    condition = db.scalar(
        select(models.DecisionCondition).where(
            models.DecisionCondition.decision_id == decision.id,
            models.DecisionCondition.user_id == current_user.id,
        )
    )

    values = request.model_dump()
    if condition is None:
        condition = models.DecisionCondition(
            decision_id=decision.id,
            user_id=current_user.id,
            **values,
        )
        db.add(condition)
    else:
        for field, value in values.items():
            setattr(condition, field, value)

    db.commit()
    db.refresh(condition)
    return condition


@app.get(
    "/decisions/{decision_id}/conditions/me",
    response_model=schemas.DecisionConditionRead,
)
def read_my_decision_condition(
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = get_decision_for_current_couple(
        db,
        decision_id,
        current_user,
    )
    condition = db.scalar(
        select(models.DecisionCondition).where(
            models.DecisionCondition.decision_id == decision.id,
            models.DecisionCondition.user_id == current_user.id,
        )
    )
    if condition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conditions not found",
        )
    return condition


@app.get(
    "/decisions/{decision_id}/conditions/status",
    response_model=schemas.DecisionConditionStatusRead,
)
def read_decision_condition_status(
    decision_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = get_decision_for_current_couple(
        db,
        decision_id,
        current_user,
    )
    couple = get_couple_with_members(db, decision.couple_id)
    members = [] if couple is None else couple.members
    submitted_user_ids = set(
        db.scalars(
            select(models.DecisionCondition.user_id).where(
                models.DecisionCondition.decision_id == decision.id
            )
        ).all()
    )

    member_conditions = [
        schemas.DecisionConditionMemberStatusRead(
            user_id=member.id,
            submitted=member.id in submitted_user_ids,
        )
        for member in sorted(members, key=lambda item: item.id)
    ]
    return schemas.DecisionConditionStatusRead(
        decision_id=decision.id,
        submitted_count=sum(
            item.submitted for item in member_conditions
        ),
        member_conditions=member_conditions,
    )


@app.post(
    "/decisions/{decision_id}/recommendations",
    response_model=schemas.RecommendationRead,
    status_code=status.HTTP_201_CREATED,
)
def recommend_candidate(
    decision_id: int,
    request: schemas.RecommendationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """One-shot, private, deterministic choice from user-supplied demo options.

    Scores and individual private preferences never leave the server.
    This does not claim real price or booking verification.
    """
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )

    decision = get_decision_for_current_couple(db, decision_id, current_user)
    if decision.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Decision is already closed",
        )

    attempt_id = db.scalar(
        select(models.DecisionRecommendationAttempt.id).where(
            models.DecisionRecommendationAttempt.decision_id == decision.id
        )
    )
    if attempt_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recommendation already attempted for this decision",
        )

    candidate_id = db.scalar(
        select(models.DecisionCandidate.id).where(
            models.DecisionCandidate.decision_id == decision.id
        )
    )
    if candidate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recommendation only available before first candidate",
        )

    couple = get_couple_with_members(db, decision.couple_id)
    member_ids = set() if couple is None else {member.id for member in couple.members}
    conditions = list(db.scalars(
        select(models.DecisionCondition).where(
            models.DecisionCondition.decision_id == decision.id,
            models.DecisionCondition.user_id.in_(member_ids),
        )
    ).all())
    if len(member_ids) != 2 or {item.user_id for item in conditions} != member_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Both couple members must submit conditions before recommendation",
        )

    selected = choose_balanced_option(request.options, conditions)
    attempt = models.DecisionRecommendationAttempt(
        decision_id=decision.id,
        requested_by_id=current_user.id,
        outcome="selected" if selected is not None else "no_match",
    )

    candidate = None
    try:
        db.add(attempt)
        if selected is not None:
            # The input price is only a demo estimate. Make this explicit in
            # the final Candidate text shown to BOTH people before approval.
            candidate = models.DecisionCandidate(
                decision_id=decision.id,
                content=(
                    f"{selected.title} / {selected.time_slot} / "
                    f"2인 총액 {selected.estimated_total_cost_krw:,}원"
                    "(시연용·확인 필요)"
                ),
                version=1,
                is_current=True,
            )
            db.add(candidate)
            db.flush()
            attempt.candidate_id = candidate.id
        # Persist even a no-match attempt, preventing repeated condition probes.
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recommendation request conflicted with another update",
        ) from error

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No mutually suitable option; try a manual candidate",
        )

    db.refresh(candidate)
    return schemas.RecommendationRead(
        policy_version="balanced_rules_v1",
        message=(
            "두 사람이 수용 가능한 시연용 후보를 선정했습니다. "
            "실제 가격과 예약 가능 여부를 확인하세요."
        ),
        candidate=schemas.DecisionCandidateRead.model_validate(candidate),
    )


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

    couple = get_couple_with_members(db, decision.couple_id)
    member_ids = (
        set()
        if couple is None
        else {member.id for member in couple.members}
    )
    submitted_user_ids = set(
        db.scalars(
            select(models.DecisionCondition.user_id).where(
                models.DecisionCondition.decision_id == decision.id,
                models.DecisionCondition.user_id.in_(member_ids),
            )
        ).all()
    )
    if len(member_ids) != 2 or not member_ids.issubset(
        submitted_user_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Both couple members must submit conditions before "
                "candidate creation"
            ),
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
        db.add(models.DecisionConfirmation(
            decision_id=decision.id,
            candidate_id=candidate.id,
            candidate_version=candidate.version,
            content_snapshot=candidate.content,
        ))

    db.commit()
    db.refresh(approval)

    return approval


@app.get(
    "/decision-confirmations",
    response_model=list[schemas.DecisionConfirmationRead],
)
def read_decision_confirmations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.couple_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User does not belong to a couple",
        )
    return list(db.scalars(
        select(models.DecisionConfirmation)
        .join(models.Decision)
        .where(models.Decision.couple_id == current_user.couple_id)
        .order_by(models.DecisionConfirmation.id.desc())
    ).all())

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
