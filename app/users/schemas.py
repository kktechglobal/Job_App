# from pydantic import BaseModel, EmailStr, Field
# from datetime import datetime
# from typing import Optional, List
# from app.users.schemas import UserRole,login,logout

# # Auth & User Schemas
# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class UserCreate(BaseModel):
#     email: EmailStr
#     password: str
#     full_name: str
#     role: UserRole

# class UserResponse(BaseModel):
#     id: int
#     email: EmailStr
#     full_name: str
#     role: UserRole
#     is_active: bool

#     class Config:
#         from_attributes = True

# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str


# class UserLogout(BaseModel):
#     message: str = Field(default="Successfully logged out")