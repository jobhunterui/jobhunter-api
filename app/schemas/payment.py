from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime

# --- Request Schemas ---

class InitializePaymentRequest(BaseModel):
    email: EmailStr
    plan_identifier: str # e.g., "monthly", "yearly" - maps to plan codes in config
    callback_url: HttpUrl

# --- Response Schemas ---

class InitializePaymentResponseData(BaseModel):
    authorization_url: HttpUrl
    access_code: str
    reference: str

class InitializePaymentResponse(BaseModel):
    status: bool
    message: str
    data: InitializePaymentResponseData

# --- Paystack Webhook Schemas ---
# These are simplified. Paystack sends a lot more data.
# You can expand these based on the specific event data you need.

class PaystackWebhookCustomer(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    customer_code: str
    phone: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PaystackWebhookAuthorization(BaseModel):
    authorization_code: str
    bin: str
    last4: str
    exp_month: str
    exp_year: str
    channel: str
    card_type: str
    bank: str
    country_code: str
    brand: str
    reusable: bool
    signature: Optional[str] = None # Sometimes present
    account_name: Optional[str] = None

class PaystackWebhookPlan(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    plan_code: Optional[str] = None
    interval: Optional[str] = None # e.g., "monthly", "annually"

class PaystackWebhookSubscriptionData(BaseModel): # For subscription events
    id: Optional[int] = None # Subscription ID from Paystack
    domain: str
    status: str # e.g., "active", "non-renewing", "cancelled"
    subscription_code: str
    amount: int # In kobo or smallest currency unit
    cron_expression: str
    next_payment_date: Optional[datetime] = None
    open_invoice: Optional[str] = None # Invoice code
    plan: PaystackWebhookPlan
    authorization: PaystackWebhookAuthorization
    customer: PaystackWebhookCustomer
    created_at: datetime
    # Add more fields as needed from Paystack docs for subscription events

class PaystackWebhookChargeData(BaseModel): # For charge.success event
    id: int # Charge ID
    domain: str
    status: str # "success", "failed", etc.
    reference: str
    amount: int # In kobo or smallest currency unit
    paid_at: datetime
    created_at: datetime
    channel: str
    currency: str
    ip_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None # Important if you pass custom metadata like UID
    customer: PaystackWebhookCustomer
    authorization: PaystackWebhookAuthorization
    plan: Optional[PaystackWebhookPlan] = None # May not always be present for one-time charges
    # For charges linked to a subscription, plan_object or plan might be present
    plan_object: Optional[PaystackWebhookPlan] = None # Often contains plan details for subscription payments


class PaystackWebhookEvent(BaseModel):
    event: str # e.g., "charge.success", "subscription.create", "subscription.disable"
    data: Dict[str, Any] # Initially a dict, then parse into specific model

    # Parsed specific data models based on event type
    # These are illustrative. You'll pick one in the webhook logic.
    # charge_data: Optional[PaystackWebhookChargeData] = None
    # subscription_data: Optional[PaystackWebhookSubscriptionData] = None


# Example of how you might structure the data within an event
class PaystackChargeSuccessData(PaystackWebhookChargeData):
    # any charge.success specific overrides or additions
    pass

class PaystackSubscriptionCreateData(PaystackWebhookSubscriptionData):
    # any subscription.create specific overrides or additions
    pass

class PaystackSubscriptionDisableData(PaystackWebhookSubscriptionData):
    # any subscription.disable specific overrides or additions
    pass

class PaystackSubscriptionNotRenewData(PaystackWebhookSubscriptionData):
    # any subscription.not_renew specific overrides or additions
    pass