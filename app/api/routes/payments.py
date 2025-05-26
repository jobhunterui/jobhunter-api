import httpx
import hmac
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from starlette import status
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta

from app.api.dependencies import get_current_active_user_uid, get_current_user
from app.schemas.payment import (
    InitializePaymentRequest,
    InitializePaymentResponse,
    InitializePaymentResponseData,
    PaystackWebhookEvent,
    PaystackChargeSuccessData,
    PaystackSubscriptionCreateData,
    PaystackSubscriptionDisableData,
    PaystackSubscriptionNotRenewData
)
from app.services import user_service
from app.core.config import settings

router = APIRouter()

PAYSTACK_API_BASE_URL = "https://api.paystack.co"

@router.post(
    "/initialize_transaction",
    response_model=InitializePaymentResponse,
    summary="Initialize a Paystack transaction for a subscription plan",
    tags=["Payments"]
)
async def initialize_transaction(
    payload: InitializePaymentRequest,
    current_user_data: dict = Depends(get_current_user),
):
    """
    Initializes a Paystack transaction with detailed debugging.
    """
    user_uid = current_user_data.get("uid")
    user_email = current_user_data.get("email")
    is_production = settings.ENVIRONMENT.lower().strip() == "production"

    if not user_uid or not user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User information not found in token."
        )

    if payload.email != user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload email does not match authenticated user's email."
        )

    # Debug: Log the plan lookup
    plan_code = settings.PAYSTACK_PLAN_CODES.get(payload.plan_identifier)
    print(f"DEBUG: [Payments] Plan lookup - identifier: {payload.plan_identifier}, code: {plan_code}")
    print(f"DEBUG: [Payments] Available plans: {settings.PAYSTACK_PLAN_CODES}")
    print(f"DEBUG: [Payments] Environment: {settings.ENVIRONMENT}")
    print(f"DEBUG: [Payments] Using {'LIVE' if is_production else 'TEST'} Paystack keys")
    
    if not plan_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan identifier: {payload.plan_identifier}. Available: {list(settings.PAYSTACK_PLAN_CODES.keys())}"
        )

    headers = {
        "Authorization": f"Bearer {settings.FINAL_PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    
    # Generate a unique reference for the transaction
    transaction_reference = f"jh_{user_uid}_{payload.plan_identifier}_{int(datetime.now(timezone.utc).timestamp())}"

    # CRITICAL: For subscriptions, do NOT include amount when using plan
    data = {
        "email": payload.email,
        "plan": plan_code,  # This contains the amount - don't add amount field
        "callback_url": str(payload.callback_url),
        "reference": transaction_reference,
        "metadata": {
            "user_id": user_uid,
            "plan_identifier": payload.plan_identifier,
            "custom_fields": [
                {"display_name": "User ID", "variable_name": "user_id", "value": user_uid},
                {"display_name": "Service", "variable_name": "service_name", "value": settings.PROJECT_NAME}
            ]
        }
    }
    
    # Debug: Log the request being sent to Paystack
    print(f"DEBUG: [Payments] Paystack request data: {json.dumps(data, indent=2)}")
    print(f"DEBUG: [Payments] Secret key prefix: {settings.FINAL_PAYSTACK_SECRET_KEY[:15]}...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{PAYSTACK_API_BASE_URL}/transaction/initialize",
                headers=headers,
                json=data
            )
            
            # Debug: Log the response
            print(f"DEBUG: [Payments] Paystack response status: {response.status_code}")
            print(f"DEBUG: [Payments] Paystack response headers: {dict(response.headers)}")
            
            try:
                response_text = response.text
                print(f"DEBUG: [Payments] Paystack response body: {response_text}")
            except:
                print("DEBUG: [Payments] Could not read response body")
            
            response.raise_for_status()
            paystack_response_data = response.json()

            if paystack_response_data.get("status"):
                if not is_production:
                    print(f"INFO: Payment initialized for user {user_uid}, plan {payload.plan_identifier}")
                else:
                    print(f"INFO: [Payments] Transaction initialized successfully")
                
                return InitializePaymentResponse(
                    status=True,
                    message="Transaction initialized successfully.",
                    data=InitializePaymentResponseData(**paystack_response_data.get("data"))
                )
            else:
                print(f"ERROR: [Payments] Paystack returned status=false: {paystack_response_data}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Paystack error: {paystack_response_data.get('message', 'Unknown error')}"
                )
        except httpx.HTTPStatusError as e:
            error_detail = "Error initializing payment with Paystack."
            try:
                error_body = e.response.json()
                error_detail = f"Paystack API error: {error_body.get('message', e.response.text)}"
                print(f"ERROR: [Payments] Paystack error response: {json.dumps(error_body, indent=2)}")
            except Exception:
                print(f"ERROR: [Payments] Could not parse error response: {e.response.text}")
            
            print(f"ERROR: [Payments] HTTP {e.response.status_code}: {error_detail}")
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            print(f"ERROR: [Payments] Network error: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Network error contacting Paystack: {e}")
        except Exception as e:
            print(f"ERROR: [Payments] Unexpected error: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

# Add a new endpoint to verify your plans exist
@router.get("/debug/verify-plans", tags=["Debug"])
async def verify_plans():
    """Debug endpoint to verify plan codes exist in Paystack"""
    headers = {
        "Authorization": f"Bearer {settings.FINAL_PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    
    results = {}
    async with httpx.AsyncClient() as client:
        for plan_name, plan_code in settings.PAYSTACK_PLAN_CODES.items():
            try:
                response = await client.get(
                    f"{PAYSTACK_API_BASE_URL}/plan/{plan_code}",
                    headers=headers
                )
                if response.status_code == 200:
                    plan_data = response.json()
                    results[plan_name] = {
                        "exists": True,
                        "plan_code": plan_code,
                        "name": plan_data.get("data", {}).get("name"),
                        "amount": plan_data.get("data", {}).get("amount"),
                        "interval": plan_data.get("data", {}).get("interval"),
                        "currency": plan_data.get("data", {}).get("currency")
                    }
                else:
                    results[plan_name] = {
                        "exists": False,
                        "plan_code": plan_code,
                        "error": f"HTTP {response.status_code}"
                    }
            except Exception as e:
                results[plan_name] = {
                    "exists": False,
                    "plan_code": plan_code,
                    "error": str(e)
                }
    
    return {
        "environment": settings.ENVIRONMENT,
        "using_live_keys": settings.ENVIRONMENT.lower() == "production",
        "plans": results
    }


@router.post(
    "/webhook",
    summary="Receive webhook events from Paystack",
    status_code=status.HTTP_200_OK, # Always return 200 to Paystack if received
    tags=["Payments"]
)
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None) # Paystack sends signature in this header
):
    """
    Handles webhook events from Paystack.
    Verifies the signature and processes events like 'charge.success',
    'subscription.create', 'subscription.disable', etc.
    """
    is_production = settings.ENVIRONMENT.lower().strip() == "production"
    
    if not x_paystack_signature:
        if not is_production:
            print("Webhook error: Missing X-Paystack-Signature header")
        else:
            print("ERROR: [Webhook] Missing signature header")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Paystack signature.")

    try:
        raw_body = await request.body()
        payload_json = raw_body.decode('utf-8')
    except Exception as e:
        if not is_production:
            print(f"Webhook error: Could not decode request body: {e}")
        else:
            print("ERROR: [Webhook] Could not decode request body")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request body.")

    # Verify the webhook signature
    expected_signature = hmac.new(
        settings.FINAL_PAYSTACK_SECRET_KEY.encode('utf-8'),
        raw_body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_paystack_signature):
        if not is_production:
            print(f"Webhook error: Invalid signature. Expected: {expected_signature}, Got: {x_paystack_signature}")
        else:
            print("ERROR: [Webhook] Invalid signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Paystack signature.")

    try:
        event_payload = PaystackWebhookEvent.model_validate_json(payload_json)
        event_data = event_payload.data # This is the raw data dict from Paystack
        event_type = event_payload.event
        if not is_production:
            print(f"Received Paystack webhook event: {event_type}")
        else:
            print(f"INFO: [Webhook] Received event: {event_type}")
    except Exception as e:
        if not is_production:
            print(f"Webhook error: Could not parse webhook payload: {e}")
        else:
            print("ERROR: [Webhook] Could not parse payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook payload: {e}")

    # --- Process different event types ---
    user_uid_from_event: Optional[str] = None

    # Attempt to get user_uid from metadata (preferred) or reference
    if 'metadata' in event_data and isinstance(event_data['metadata'], dict):
        user_uid_from_event = event_data['metadata'].get('user_id')
    
    if not user_uid_from_event and 'reference' in event_data:
        # Fallback: try to parse from reference if it follows "jh_UID_plan_timestamp"
        parts = event_data['reference'].split('_')
        if len(parts) >= 2 and parts[0] == 'jh':
            user_uid_from_event = parts[1]

    if not user_uid_from_event and 'customer' in event_data and 'email' in event_data['customer']:
        # Fallback: If UID not in metadata or reference, try to find user by email.
        # This is less ideal as emails might not be unique if you allow it.
        # For this app, Firebase UID is the primary key.
        # You might need a function: async def get_user_uid_by_email(email: str) -> Optional[str]:
        if not is_production:
            print(f"Warning: UID not found directly in webhook metadata/reference for event {event_type}. Customer email: {event_data['customer']['email']}")
        else:
            print(f"WARN: [Webhook] UID not found in event data for {event_type}")
        # For now, we'll skip if UID isn't directly available to avoid ambiguity.

    if not user_uid_from_event:
        # CRITICAL: Payment received but can't identify user
        if not is_production:
            print(f"CRITICAL WEBHOOK ERROR: Payment received but cannot determine user UID for event: {event_type}")
            print(f"Full event data for manual processing: {json.dumps(event_data)}")
        else:
            print(f"CRITICAL: [Webhook] Cannot identify user for event {event_type}")
        
        # Try to extract any identifying information for manual recovery
        customer_email = None
        if 'customer' in event_data and 'email' in event_data.get('customer', {}):
            customer_email = event_data['customer']['email']
            if not is_production:
                print(f"Customer email found: {customer_email} - Manual intervention required")
        
        # Log critical information for manual recovery
        critical_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "customer_email": customer_email,
            "requires_manual_processing": True
        }
        print(f"MANUAL_RECOVERY_REQUIRED: {json.dumps(critical_log)}")
        
        # IMPORTANT: Still return success to Paystack to prevent endless retries
        # This needs manual intervention but we don't want Paystack to keep retrying
        return {"status": "success", "message": "Webhook received - manual processing required"}

    # Process based on event type
    if event_type == "charge.success":
        try:
            charge_data = PaystackChargeSuccessData(**event_data)
            if not is_production:
                print(f"Processing charge.success for user {user_uid_from_event}, reference: {charge_data.reference}")
            else:
                print(f"INFO: [Webhook] Processing charge.success")
            
            # This event signifies a successful payment.
            # If this charge is part of creating/renewing a subscription,
            # the subscription.* events are usually more specific for managing access.
            # However, you might log this payment or use it if you have one-off purchases.

            # If the charge is for a subscription, update based on plan details.
            if charge_data.plan_object and charge_data.plan_object.plan_code:
                # Determine tier from plan_code
                # This mapping logic could be more sophisticated
                tier = "free" # default
                for plan_name, p_code in settings.PAYSTACK_PLAN_CODES.items():
                    if p_code == charge_data.plan_object.plan_code:
                        tier = f"pro_{plan_name}" # e.g. pro_monthly
                        break
                
                # Estimate subscription end date based on plan interval (monthly/annually)
                # Paystack's subscription.* events often provide more accurate next_payment_date
                ends_at = charge_data.paid_at # Start with paid_at
                if charge_data.plan_object.interval == "monthly":
                    ends_at += timedelta(days=31) # Approximate, Paystack gives exact via subscription events
                elif charge_data.plan_object.interval == "annually":
                    ends_at += timedelta(days=366) # Approximate

                await user_service.update_user_subscription_from_paystack(
                    uid=user_uid_from_event,
                    tier=tier,
                    status="active", # Assuming charge.success for a plan means it's active
                    paystack_subscription_id=charge_data.authorization.authorization_code, # Or from a subscription event
                    paystack_customer_id=charge_data.customer.customer_code,
                    current_period_starts_at=charge_data.paid_at,
                    current_period_ends_at=ends_at
                )
            else:
                if not is_production:
                    print(f"Charge.success for user {user_uid_from_event} was not tied to a known plan via plan_object.")

        except Exception as e:
            if not is_production:
                print(f"Error processing charge.success for {user_uid_from_event}: {e}")
            else:
                print(f"ERROR: [Webhook] Error processing charge.success: {str(e)}")
            # Log error but return 200 to Paystack

    elif event_type == "subscription.create":
        try:
            sub_data = PaystackSubscriptionCreateData(**event_data)
            if not is_production:
                print(f"Processing subscription.create for user {user_uid_from_event}, sub_code: {sub_data.subscription_code}")
            else:
                print(f"INFO: [Webhook] Processing subscription.create")
            
            tier = "free"
            for plan_name, p_code in settings.PAYSTACK_PLAN_CODES.items():
                if p_code == sub_data.plan.plan_code:
                    tier = f"pro_{plan_name}"
                    break

            await user_service.update_user_subscription_from_paystack(
                uid=user_uid_from_event,
                tier=tier,
                status=sub_data.status, # "active"
                paystack_subscription_id=sub_data.subscription_code,
                paystack_customer_id=sub_data.customer.customer_code,
                current_period_starts_at=sub_data.created_at, # Or a more specific field if available
                current_period_ends_at=sub_data.next_payment_date # This is usually the key field
            )
        except Exception as e:
            if not is_production:
                print(f"Error processing subscription.create for {user_uid_from_event}: {e}")
            else:
                print(f"ERROR: [Webhook] Error processing subscription.create: {str(e)}")

    elif event_type in ["subscription.disable", "subscription.not_renew", "subscription.expiring_cards"]: # Handle disable and non-renewal
        try:
            sub_data = PaystackSubscriptionDisableData(**event_data) # Schema can be reused or made specific
            if not is_production:
                print(f"Processing {event_type} for user {user_uid_from_event}, sub_code: {sub_data.subscription_code}")
            else:
                print(f"INFO: [Webhook] Processing {event_type}")

            # If subscription.disable, it means it's no longer active. Revert to free.
            # If subscription.not_renew, it means it will expire at next_payment_date.
            # You might want to update the status to "non-renewing" and set a cancellation_effective_date.
            
            effective_status = "cancelled" # if subscription.disable
            cancellation_date = sub_data.next_payment_date # typically when access ends

            if event_type == "subscription.not_renew":
                effective_status = "non-renewing" # Or keep "active" until next_payment_date
                # The user retains access until current_period_ends_at (which is next_payment_date)
                # Update the subscription to reflect it won't renew.
                
                # For now, let's simplify: if it's not renewing or disabled, eventually they go to free.
                # More nuanced logic: if 'not_renew', keep active, set cancellation_effective_date.
                # A separate cron job/check could then revert to free when that date passes.
                
                # For simplicity here: if disabled, revert now. if not_renew, set status and cancellation_date
                if sub_data.status == "cancelled" or sub_data.status == "complete" or event_type == "subscription.disable":
                    await user_service.revert_user_to_free_tier(uid=user_uid_from_event)
                else: # e.g. status is 'non-renewing' or 'active' but event is 'not_renew'
                    tier = "free" # Determine original tier if needed for logging
                    for plan_name, p_code in settings.PAYSTACK_PLAN_CODES.items():
                        if p_code == sub_data.plan.plan_code:
                            tier = f"pro_{plan_name}" # Keep their current tier name
                            break
                    await user_service.update_user_subscription_from_paystack(
                        uid=user_uid_from_event,
                        tier=tier, # Keep current tier name
                        status=sub_data.status if sub_data.status == "non-renewing" else "non-renewing",
                        paystack_subscription_id=sub_data.subscription_code,
                        paystack_customer_id=sub_data.customer.customer_code,
                        current_period_starts_at=sub_data.created_at, # Or last invoice period start
                        current_period_ends_at=sub_data.next_payment_date,
                        cancellation_effective_date=sub_data.next_payment_date # Access ends here
                    )

        except Exception as e:
            if not is_production:
                print(f"Error processing {event_type} for {user_uid_from_event}: {e}")
            else:
                print(f"ERROR: [Webhook] Error processing {event_type}: {str(e)}")
    
    # Add more event handlers as needed:
    # - invoice.payment_failed, invoice.update, customeridentification.failed, etc.

    # Acknowledge receipt of the webhook
    return {"status": "success", "message": "Webhook received successfully."}

class AppConfigResponse(BaseModel):
    environment: str
    paystack_public_key: str
    # Add any other config frontend might need

@router.get("/app-config", response_model=AppConfigResponse, tags=["App Configuration"])
async def get_app_configuration():
    """
    Provides essential configuration to the frontend, like the current environment
    and the correct Paystack public key.
    """
    if not settings.PAYSTACK_PUBLIC_KEY or "placeholder" in settings.PAYSTACK_PUBLIC_KEY:
        print("CRITICAL: Attempted to send unconfigured Paystack public key to frontend.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Payment system configuration is incomplete on the server."
        )
    
    # Secure logging for production
    is_production = settings.ENVIRONMENT.lower().strip() == "production"
    if not is_production:
        print(f"INFO: App config requested - Environment: {settings.ENVIRONMENT}")
    
    return AppConfigResponse(
        environment=settings.ENVIRONMENT,
        paystack_public_key=settings.FINAL_PAYSTACK_PUBLIC_KEY
    )