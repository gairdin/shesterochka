from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class User(BaseModel):
    name: str
    email: EmailStr


class AdminUser(BaseModel):
    username: str
    password: str


class Promotion(BaseModel):
    id: str = Field(..., alias="_id")
    title: str
    description: str
    start_date: str
    end_date: str