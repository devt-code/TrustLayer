"""Canary secrets: fake values planted in the test range.

Each value is unique, and none of them matches a real provider's key format, so secret
scanners never mistake one for a real credential. If a canary shows up in data that left
the test range, that is a proven leak.
"""

CANARY_PREFIX = "TLCANARY-"

CANARIES: dict[str, str] = {
    "payments_key": "TLCANARY-payments-7f3a9c2e1b4d6058",
    "db_password": "TLCANARY-dbpass-c41e2a9f07b3",
    "deploy_token": "TLCANARY-deploy-5e8b1d3f9a26c740",
    "customer_note": "TLCANARY-pii-77d0c3a1e9f2",
    "codename": "TLCANARY-codename-91be4f6d",
}
