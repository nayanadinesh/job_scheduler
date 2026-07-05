from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import ConflictError, UnauthorizedError
from app.core.response import created, ok
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.auth import Organization, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")

    org = Organization(name=body.org_name)
    db.add(org)
    await db.flush()

    user = User(org_id=org.id, email=body.email, password_hash=hash_password(body.password), role="owner")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=user.id, extra={"org_id": org.id})
    return created({"user": UserOut.model_validate(user).model_dump(mode="json"), "access_token": token, "token_type": "bearer"})


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    token = create_access_token(subject=user.id, extra={"org_id": user.org_id})
    return ok({"access_token": token, "token_type": "bearer"})


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return ok(UserOut.model_validate(current_user).model_dump(mode="json"))
