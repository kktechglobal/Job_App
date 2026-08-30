from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from candidate_profile.schemas import (
     ApplicationStatusUpdate, CandidateProfileCreate, CandidateProfileUpdate,
    ChangeName, ChangePassword, CompanyCreate, CompanyUpdate, Contact, FeatureJob,
    ForgotPassword, InterviewCreate, InterviewUpdate, JobCreate, JobUpdate, LoginUser,
    LogoutRequest, RegisterUser, Registration,candidate_id, ResetPassword, SavedCardCreate, SocialLinkCreate,
)


from services import service

router = APIRouter()








# ---------------------------- Candidate profile ----------------------------

@router.post("/api/candidate/profile", status_code=status.HTTP_201_CREATED)
def create_candidate_profile(body: CandidateProfileCreate, current_candidate_id: int = Depends(candidate_id)):
    if current_candidate_id in service.profiles:
        raise HTTPException(409, "Profile already exists")
    profile = {"id": service.next_profile_id, "candidate_id": current_candidate_id, **body.model_dump(mode="json")}
    service.profiles[current_candidate_id] = profile
    service.candidate_links[current_candidate_id] = []
    service.next_profile_id += 1
    return profile


@router.get("/api/candidate/profile")
def get_candidate_profile(current_candidate_id: int = Depends(candidate_id)):
    return service.candidate_profile(current_candidate_id)


@router.patch("/api/candidate/profile")
def update_candidate_profile(body: CandidateProfileUpdate, current_candidate_id: int = Depends(candidate_id)):
    profile = service.candidate_profile(current_candidate_id)
    profile.update(body.model_dump(exclude_unset=True, mode="json"))
    return profile


@router.get("/api/candidate/profile/skills")
def get_candidate_skills(current_candidate_id: int = Depends(candidate_id)):
    return service.candidate_profile(current_candidate_id)["skills"]


@router.get("/api/candidate/profile/social-links")
def get_candidate_links(current_candidate_id: int = Depends(candidate_id)):
    service.candidate_profile(current_candidate_id)
    return service.candidate_links[current_candidate_id]


@router.post("/api/candidate/profile/social-links", status_code=status.HTTP_201_CREATED)
def add_candidate_link(body: SocialLinkCreate, current_candidate_id: int = Depends(candidate_id)):
    service.candidate_profile(current_candidate_id)
    links = service.candidate_links[current_candidate_id]
    if any(link["platform"] == body.platform for link in links):
        raise HTTPException(409, f"{body.platform} link already exists")
    link = {"id": service.next_link_id, **body.model_dump(mode="json")}
    links.append(link)
    service.next_link_id += 1
    return link


@router.delete("/api/candidate/profile/social-links/{link_id}", status_code=204)
def delete_candidate_link(link_id: int, current_candidate_id: int = Depends(candidate_id)):
    service.candidate_profile(current_candidate_id)
    links = service.candidate_links[current_candidate_id]
    link = next((item for item in links if item["id"] == link_id), None)
    if not link:
        raise HTTPException(404, "Social link not found")
    links.remove(link)
    return Response(status_code=204)