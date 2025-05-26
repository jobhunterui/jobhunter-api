# app/schemas/user.py
from pydantic import BaseModel, EmailStr, field_validator
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
    
    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v):
        # Ensure tier is a string and handle None
        if v is None:
            return "free"
        return str(v).lower()
    
    @field_validator('status')
    @classmethod 
    def validate_status(cls, v):
        # Ensure status is a string and handle None
        if v is None:
            return "active"
        return str(v).lower()

class UserProfileResponse(BaseModel):
    uid: str
    email: EmailStr
    created_at: datetime
    subscription: UserSubscription
    
    @field_validator('created_at')
    @classmethod
    def validate_created_at(cls, v):
        # Ensure datetime has timezone info
        if isinstance(v, datetime) and v.tzinfo is None:
            from datetime import timezone
            return v.replace(tzinfo=timezone.utc)
        return v

class UserDBCreate(BaseModel):
    uid: str
    email: EmailStr
    created_at: datetime
    subscription: UserSubscription