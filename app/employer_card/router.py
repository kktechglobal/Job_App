from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.employer_card.schemas import (
    ApplicationStatusUpdate,employer_id, EmployerProfileCreate, EmployerProfileUpdate,
    ChangeName, ChangePassword, CompanyCreate, CompanyUpdate, Contact, FeatureJob,
    ForgotPassword, InterviewCreate, InterviewUpdate, JobCreate, JobUpdate, LoginUser,
    LogoutRequest, RegisterUser, Registration, ResetPassword, SavedCardCreate, SocialLinkCreate,
)
from app.employer_card import service

router = APIRouter()










# ---------------------------- Saved cards ----------------------------

@router.post("/employer/me/cards", status_code=status.HTTP_201_CREATED)
def save_card(body: SavedCardCreate, current_employer_id: int = Depends(employer_id)):
    cards = service.cards.setdefault(current_employer_id, [])
    card = {"id": service.next_card_id, **body.model_dump(), "is_default": not cards}
    cards.append(card)
    service.next_card_id += 1
    return card


@router.get("/employer/me/cards")
def get_cards(current_employer_id: int = Depends(employer_id)):
    return service.cards.get(current_employer_id, [])


def card_or_404(employer: int, card_id: int) -> dict:
    card = next((item for item in service.cards.get(employer, []) if item["id"] == card_id), None)
    if not card:
        raise HTTPException(404, "Saved card not found")
    return card


@router.patch("/employer/me/cards/{card_id}/default")
def set_default_card(card_id: int, current_employer_id: int = Depends(employer_id)):
    selected = card_or_404(current_employer_id, card_id)
    for card in service.cards[current_employer_id]:
        card["is_default"] = card["id"] == selected["id"]
    return selected


@router.delete("/employer/me/cards/{card_id}", status_code=204)
def delete_card(card_id: int, current_employer_id: int = Depends(employer_id)):
    card = card_or_404(current_employer_id, card_id)
    service.cards[current_employer_id].remove(card)
    if card["is_default"] and service.cards[current_employer_id]:
        service.cards[current_employer_id][0]["is_default"] = True
    return Response(status_code=204)