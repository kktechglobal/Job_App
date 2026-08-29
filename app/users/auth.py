
# from fastapi import APIRouter, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from app.database.db import get_session as get_db
# from app.core.security import verify_password, create_access_token
# from app.users.schemas import UserCreate, UserResponse, Token
# from app.users.service import UserService
# from app.users.models import User

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

# @router.post("/logout", response_model=Token)
# async def logout():
#     pass


#     access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
#     return {"access_token": access_token, "token_type": "bearer"}




#-------------------------------------------------------------------------




# # from fastapi import APIRouter, HTTPException
# # from app.users.auth import UserCreate, UserLogin

# # router = APIRouter(
# #     prefix="/auth",
# #     tags=["Authentication"]
# # )

# # users = []



# # @router.post("/register")
# # def create_account(user: UserCreate):

# #     # Check if email already exists
# #         for existing_user in users:
# #             if existing_user["email"] == user.email:
# #                 raise HTTPException(
# #                 status_code=400,
# #                 detail="Email already registered")

            
# #         new_user = {
# #         "id": len(users) + 1,
# #         "full_name": user.full_name,
# #         "email": user.email,
# #         "password": user.password,
# #         "role": user.role
# #     }

# #         users.append(new_user)
# #         return {
# #         "message": "Account created successfully",
# #         "user": {
# #             "id": new_user["id"],
# #             "full_name": new_user["full_name"],
# #             "email": new_user["email"],
# #             "role": new_user["role"]
# #         }
# #     }




# # @router.post("/login")
# # def login(user: UserLogin):

# #     # Find user by email
# #         for existing_user in users:

# #             if existing_user["email"] == user.email:

# #             # Check password
# #                 if existing_user["password"] != user.password:
# #                     raise HTTPException(
# #                     status_code=401,
# #                     detail="Incorrect password"
# #                 )

# #             return {
# #                 "message": "Login successful",
# #                 "user": {
# #                     "id": existing_user["id"],
# #                     "full_name": existing_user["full_name"],
# #                     "email": existing_user["email"],
# #                     "role": existing_user["role"]
# #                 }
# #             }

# #             raise HTTPException(
# #             status_code=401,
# #             detail="Invalid email or password"
# #     )



    