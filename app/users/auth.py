from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi import FastAPI
import jwt
from app.core.security import candidate_id
from app.users.schemas import (CandidateProfileCreate, CandidateProfileUpdate, SocialLinkCreate,)
from app.users.service import UserService


router = APIRouter(tags=["Candidate Profile"])

service = UserService()

# app = FastAPI()
# app.include_router(router)



# CREATE CANDIDATE PROFILE

@router.post(
    "/api/candidate/profile",
    status_code=status.HTTP_201_CREATED)

def create_candidate_profile(
    body: CandidateProfileCreate,
    current_candidate_id: int = Depends(candidate_id),
):
    # Check if candidate already has a profile
    if current_candidate_id in service.profiles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists"
        )

    # Create profile
    profile = {
        "id": service.next_profile_id,
        "candidate_id": current_candidate_id,
        **body.model_dump(mode="json"),
    }

    # Save profile
    service.profiles[current_candidate_id] = profile

    # Create empty social-links list for candidate
    service.candidate_links[current_candidate_id] = []

    # Increase profile ID
    service.next_profile_id += 1

    return profile



# GET CANDIDATE PROFILE


@router.get("/api/candidate/profile")
def get_candidate_profile(
    current_candidate_id: int = Depends(candidate_id),):
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return profile



# UPDATE CANDIDATE PROFILE


@router.patch("/api/candidate/profile")
def update_candidate_profile(
    body: CandidateProfileUpdate,
    current_candidate_id: int = Depends(candidate_id),
):
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    # Only update fields that were provided
    profile.update(body.model_dump(exclude_unset=True, mode="json"))

    return profile



# GET CANDIDATE SKILLS


@router.get("/api/candidate/profile/skills")
def get_candidate_skills(
    current_candidate_id: int = Depends(candidate_id),
):
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return profile.get("skills", [])



# GET CANDIDATE SOCIAL LINKS


@router.get("/api/candidate/profile/social-links")
def get_candidate_links(
    current_candidate_id: int = Depends(candidate_id),
):
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    return service.candidate_links.get(
        current_candidate_id,
        []
    )



# ADD CANDIDATE SOCIAL LINK


@router.post(
    "/api/candidate/profile/social-links",
    status_code=status.HTTP_201_CREATED
)
def add_candidate_link(
    body: SocialLinkCreate,
    current_candidate_id: int = Depends(candidate_id),
):
    # Make sure profile exists
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    # Get candidate's existing links
    links = service.candidate_links.get(
        current_candidate_id,
        []
    )

    # Check if platform already exists
    if any(
link["platform"] == body.platform
        for link in links ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail=f"{body.platform} link already exists")

    # Create new link
    link = {
        "id": service.next_link_id,
        **body.model_dump(mode="json"),
    }

    # Add link
    links.append(link)

    # Save links
    service.candidate_links[current_candidate_id] = links

    # Increase link ID
    service.next_link_id += 1

    return link



# DELETE CANDIDATE SOCIAL LINK


@router.delete(
    "/api/candidate/profile/social-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_candidate_link(
    link_id: int,
    current_candidate_id: int = Depends(candidate_id),
):
    # Make sure profile exists
    profile = service.candidate_profile(current_candidate_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    # Get candidate links
    links = service.candidate_links.get(
        current_candidate_id,
        []
    )

    # Find the link
    link = next(
        (
            item
            for item in links
            if item["id"] == link_id
        ),
        None
    )

    
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social link not found")

    links.remove(link)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
































































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



    