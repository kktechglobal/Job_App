# from fastapi import APIRouter, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from app.database.db import get_session as get_db
# from app.core.security import verify_password, create_access_token
# from app.users.schemas import UserCreate, UserResponse, Token
# from app.users.service import UserService
# from app.users.models import User,require_role,users_R,job_post,EntityNotFoundException

# router = APIRouter(prefix="/auth", tags=["Authentication"])

# @router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
# async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
#     return await UserService.create_user(db, user_in)

# @router.post("/login", response_model=Token)
# async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
#     result = await db.execute(select(User).where(User.email == form_data.username))
#     user = result.scalars().first()
#     if not user or not verify_password(form_data.password, user.hashed_password):
#         raise HTTPException(status_code=400, detail="Incorrect email or password")
    
#     access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
#     return {"access_token": access_token, "token_type": "bearer"}




# admin_router = APIRouter(prefix="/admin", tags=["Admin Operations"])

# @admin_router.patch("/approve-job/{job_id}")
# async def approve_job_posting(
#     job_id: int,
#     current_user=Depends(require_role(users_R.ADMIN)),
#     db: AsyncSession = Depends(get_db)
# ):
#     res = await db.execute(select(job_post).where(job_post.id == job_id))
#     job = res.scalars().first()
#     if not job:
#         raise EntityNotFoundException("Job not found")
    
#     job.is_approved_by_admin = True
#     await db.commit()
#     return {"message": "Job posting successfully approved by admin"}