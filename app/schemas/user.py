# app/schemas/user.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSubscription(BaseModel):
    tier: str = "free"
    status: str = "active"
    paystack_customer_id: Optional[str] = None
    paystack_subscription_id: Optional[str] = None
    current_period_starts_at: Optional[datetime] = None
    current_period_ends_at: Optional[datetime] = None
    cancellation_effective_date: Optional[datetime] = None

class UserProfileResponse(BaseModel):
    uid: str
    email: EmailStr
    created_at: datetime # Or str if you prefer to format it before sending
    subscription: UserSubscription

class UserDBCreate(BaseModel):
    uid: str
    email: EmailStr
    created_at: datetime
    subscription: UserSubscription