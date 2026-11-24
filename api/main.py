import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from store import Account, LoginSession, engine

ORIGIN = os.environ["APP_ORIGIN"]
SECURE_COOKIE = ORIGIN.startswith("https://")
TOKEN_NAME = "planroom_session"
SESSION_AGE = timedelta(hours=8)
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe())
app = FastAPI(
    title="Planroom", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None
)


@app.middleware("http")
async def browser_boundary(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE"} and request.headers.get("origin") != ORIGIN:
        return JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(_request: Request, _error: RequestValidationError):
    return JSONResponse({"detail": "Check the field values and try again."}, status_code=422)


def database():
    with Session(engine) as db:
        yield db


Db = Annotated[Session, Depends(database)]
Token = Annotated[str | None, Cookie(alias=TOKEN_NAME)]


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticated_account(db: Db, token: Token = None) -> Account:
    account = db.scalar(
        select(Account)
        .join(LoginSession)
        .where(LoginSession.digest == digest(token or ""), LoginSession.expires_at > datetime.now(UTC))
    )
    if account is None:
        raise HTTPException(401, "Please sign in.")
    return account


CurrentAccount = Annotated[Account, Depends(authenticated_account)]


class Credentials(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)


class Registration(Credentials):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class SavingsPlan(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    target: int = Field(strict=True, ge=1, le=10_000_000)
    saved: int = Field(strict=True, ge=0, le=10_000_000)
    monthly: int = Field(strict=True, ge=0, le=10_000_000)


Answer = Annotated[int, Field(strict=True, ge=1, le=3)]


class Questionnaire(BaseModel):
    horizon: Answer
    reaction: Answer
    experience: Answer


class Workspace(BaseModel):
    name: str
    plan: SavingsPlan | None
    questionnaire: Questionnaire | None


def workspace(account: Account) -> Workspace:
    return Workspace(name=account.name, plan=account.plan, questionnaire=account.questionnaire)


def start_session(db: Session, account: Account, response: Response, previous: str | None):
    now = datetime.now(UTC)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    if previous:
        db.execute(delete(LoginSession).where(LoginSession.digest == digest(previous)))
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(digest=digest(token), account_id=account.id, expires_at=now + SESSION_AGE))
    result = workspace(account)
    db.commit()
    response.set_cookie(
        TOKEN_NAME, token, max_age=int(SESSION_AGE.total_seconds()),
        httponly=True, secure=SECURE_COOKIE, samesite="lax", path="/api",
    )
    return result


@app.get("/api/health/live")
def live():
    return {"status": "ok"}


@app.get("/api/health/ready")
def ready(db: Db):
    try:
        db.execute(text("SELECT 1 FROM accounts LIMIT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable.") from exc
    return {"status": "ready"}


@app.post("/api/auth/register", status_code=201)
def register(data: Registration, db: Db, response: Response, token: Token = None) -> Workspace:
    account = Account(email=data.email.lower(), name=data.name, password_hash=passwords.hash(data.password))
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "This email already has an account.") from exc
    return start_session(db, account, response, token)


@app.post("/api/auth/login")
def login(data: Credentials, db: Db, response: Response, token: Token = None) -> Workspace:
    account = db.scalar(select(Account).where(Account.email == data.email.lower()))
    valid = passwords.verify(data.password, account.password_hash if account else dummy_hash)
    if not valid or account is None:
        raise HTTPException(401, "Email or password is incorrect.")
    return start_session(db, account, response, token)


@app.post("/api/auth/demo", status_code=201)
def demo(db: Db, response: Response, token: Token = None) -> Workspace:
    account = Account(
        email=f"demo-{secrets.token_hex(12)}@example.org",
        name="Alex Morgan",
        password_hash=dummy_hash,
        plan={"title": "Emergency fund", "target": 15000, "saved": 8250, "monthly": 750},
        questionnaire={"horizon": 2, "reaction": 2, "experience": 1},
    )
    db.add(account)
    db.flush()
    return start_session(db, account, response, token)


@app.post("/api/auth/logout", status_code=204)
def logout(db: Db, response: Response, token: Token = None):
    if token:
        db.execute(delete(LoginSession).where(LoginSession.digest == digest(token)))
        db.commit()
    response.delete_cookie(TOKEN_NAME, path="/api", secure=SECURE_COOKIE, httponly=True, samesite="lax")


@app.get("/api/workspace")
def read_workspace(account: CurrentAccount) -> Workspace:
    return workspace(account)


@app.put("/api/plan")
def save_plan(plan: SavingsPlan, db: Db, account: CurrentAccount) -> SavingsPlan:
    account.plan = plan.model_dump()
    db.commit()
    return plan


@app.put("/api/questionnaire")
def save_questionnaire(questionnaire: Questionnaire, db: Db, account: CurrentAccount) -> Questionnaire:
    account.questionnaire = questionnaire.model_dump()
    db.commit()
    return questionnaire
