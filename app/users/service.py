# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from sqlalchemy import or_
# from typing import List, Optional
# from app.job_post.shemas import JobPostCreate
# from app.users.models import users, job_post, application, candidate_profile, applicationStatus, users_Role, users_create
# from app.core.security import get_password_hash
# from app.core.exceptions import DuplicateResourceException, EntityNotFoundException, IncompleteProfileException

# class UserService:
#     @staticmethod
#     async def create_user(db: AsyncSession, user_in: users_create) -> users:
#         existing = await db.execute(select(users).where(users.email == user_in.email))
#         if existing.scalars().first():
#             raise DuplicateResourceException("Email already registered")
        
#         user = users(
#             email=user_in.email,
#             hashed_password=get_password_hash(user_in.password),
#             full_name=user_in.full_name,
#             role=user_in.role
#         )
#         db.add(user)
#         await db.commit()
#         await db.refresh(user)

#         if user_in.role == users_Role.JOB_SEEKER:
#             profile = candidate_profile(user_id=user.id)
#             db.add(profile)
#             await db.commit()

#         return user

