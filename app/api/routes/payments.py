import httpx
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import RedirectResponse
from starlette import status
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta

from app.api.dependencies import get_current_active_user_uid, get_current_user
from app.schemas.payment import (
    InitializePaymentRequest,
    InitializePaymentResponse,
    InitializePaymentResponseData,
    PaystackWebhookEvent,
    PaystackChargeSuccessData, # For parsing specific event data
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
    response_model=InitializePaymentResponse, # Updated based on Paystack's actual successful response
    summary="Initialize a Paystack transaction for a subscription plan",
    tags=["Payments"]
)
async def initialize_transaction(
    payload: InitializePaymentRequest,
    current_user_data: dict = Depends(get_current_user), # Get full user data for email and uid
):
    """
    Initializes a Paystack transaction.
    The user (identified by Firebase token) provides their email, chosen plan identifier,
    and a callback URL for Paystack to redirect to after payment attempt.

    The backend uses the plan_identifier to fetch the corresponding Paystack Plan Code
    from settings.
    """
    user_uid = current_user_data.get("uid")
    user_email = current_user_data.get("email")

    if not user_uid or not user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User information not found in token."
        )

    if payload.email != user_email:
        # This check is important for security.
        # The email for Paystack should match the authenticated user's email.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload email does not match authenticated user's email."
        )

    plan_code = settings.PAYSTACK_PLAN_CODES.get(payload.plan_identifier)
    if not plan_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan identifier: {payload.plan_identifier}. Available: {list(settings.PAYSTACK_PLAN_CODES.keys())}"
        )

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    # Generate a unique reference for the transaction, including UID for easy mapping
    # Paystack references can be up to 100 characters.
    transaction_reference = f"jh_{user_uid}_{payload.plan_identifier}_{int(datetime.now(timezone.utc).timestamp())}"


    # For plan subscriptions, you typically pass the plan code.
    # If it were a one-time payment for a specific amount, you'd pass 'amount' (in kobo).
    data = {
        "email": payload.email,
        "plan": plan_code, # For subscriptions
        "callback_url": str(payload.callback_url),
        "reference": transaction_reference,
        "metadata": { # Optional: useful for storing custom data
            "user_id": user_uid,
            "plan_identifier": payload.plan_identifier,
            "custom_fields": [
                {"display_name": "User ID", "variable_name": "user_id", "value": user_uid},
                {"display_name": "Service", "variable_name": "service_name", "value": settings.PROJECT_NAME}
            ]
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{PAYSTACK_API_BASE_URL}/transaction/initialize",
                headers=headers,
                json=data
            )
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            paystack_response_data = response.json()

            if paystack_response_data.get("status"):
                return InitializePaymentResponse(
                    status=True,
                    message="Transaction initialized successfully.",
                    data=InitializePaymentResponseData(**paystack_response_data.get("data"))
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Paystack error: {paystack_response_data.get('message', 'Unknown error')}"
                )
        except httpx.HTTPStatusError as e:
            error_detail = "Error initializing payment with Paystack."
            try:
                error_body = e.response.json()
                error_detail = f"Paystack API error: {error_body.get('message', e.response.text)}"
            except Exception:
                pass # Keep generic error detail
            print(f"Paystack API HTTPStatusError: {e.response.status_code} - {error_detail}")
            raise HTTPException(status_code=e.response.status_code, detail=error_detail)
        except httpx.RequestError as e:
            print(f"Paystack API RequestError: {e}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Network error contacting Paystack: {e}")
        except Exception as e:
            print(f"Unexpected error during Paystack initialization: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")


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
    if not x_paystack_signature:
        print("Webhook error: Missing X-Paystack-Signature header")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Paystack signature.")

    try:
        raw_body = await request.body()
        payload_json = raw_body.decode('utf-8')
    except Exception as e:
        print(f"Webhook error: Could not decode request body: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request body.")

    # Verify the webhook signature
    expected_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        raw_body, # Use the raw byte body
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_paystack_signature):
        print(f"Webhook error: Invalid signature. Expected: {expected_signature}, Got: {x_paystack_signature}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Paystack signature.")

    try:
        event_payload = PaystackWebhookEvent.model_validate_json(payload_json)
        event_data = event_payload.data # This is the raw data dict from Paystack
        event_type = event_payload.event
        print(f"Received Paystack webhook event: {event_type}")
    except Exception as e:
        print(f"Webhook error: Could not parse webhook payload: {e}")
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
        print(f"Warning: UID not found directly in webhook metadata/reference for event {event_type}. Customer email: {event_data['customer']['email']}")
        # For now, we'll skip if UID isn't directly available to avoid ambiguity.
        # If you implement email lookup, ensure it's secure and handles multiple users with same email if possible.


    if not user_uid_from_event:
        print(f"Critical Webhook Error: Could not determine user UID for event: {event_type}, data: {event_data}")
        # Still return 200 to Paystack to acknowledge receipt, but log this as a critical issue.
        return {"status": "error", "message": "User UID could not be determined from webhook."}


    # Process based on event type
    if event_type == "charge.success":
        try:
            charge_data = PaystackChargeSuccessData(**event_data)
            print(f"Processing charge.success for user {user_uid_from_event}, reference: {charge_data.reference}")
            
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
                        tier = f"premium_{plan_name}" # e.g. premium_monthly
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
                print(f"Charge.success for user {user_uid_from_event} was not tied to a known plan via plan_object.")

        except Exception as e:
            print(f"Error processing charge.success for {user_uid_from_event}: {e}")
            # Log error but return 200 to Paystack


    elif event_type == "subscription.create":
        try:
            sub_data = PaystackSubscriptionCreateData(**event_data)
            print(f"Processing subscription.create for user {user_uid_from_event}, sub_code: {sub_data.subscription_code}")
            
            tier = "free"
            for plan_name, p_code in settings.PAYSTACK_PLAN_CODES.items():
                if p_code == sub_data.plan.plan_code:
                    tier = f"premium_{plan_name}"
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
            print(f"Error processing subscription.create for {user_uid_from_event}: {e}")

    elif event_type in ["subscription.disable", "subscription.not_renew", "subscription.expiring_cards"]: # Handle disable and non-renewal
        try:
            sub_data = PaystackSubscriptionDisableData(**event_data) # Schema can be reused or made specific
            print(f"Processing {event_type} for user {user_uid_from_event}, sub_code: {sub_data.subscription_code}")

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
                            tier = f"premium_{plan_name}" # Keep their current tier name
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
            print(f"Error processing {event_type} for {user_uid_from_event}: {e}")
    
    # Add more event handlers as needed:
    # - invoice.payment_failed, invoice.update, customeridentification.failed, etc.

    # Acknowledge receipt of the webhook
    return {"status": "success", "message": "Webhook received successfully."}