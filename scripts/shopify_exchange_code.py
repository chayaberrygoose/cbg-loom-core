# [FILE_ID]: scripts/SHOPIFY_EXCHANGE_CODE // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Exchanges the OAuth authorization code for a permanent
# Shopify Admin API access token.
# Step 2 of 2 — run after scripts/shopify_auth_link.py
#
# Usage:
#   python3 scripts/shopify_exchange_code.py <CODE>

import os
import sys
import requests
from dotenv import load_dotenv


def exchange_code(code: str):
    load_dotenv()

    store_url = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")
    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")

    if not store_url:
        print("[SYSTEM_DISSONANCE]: SHOPIFY_STORE_URL missing from .env")
        return
    if not client_id:
        print("[SYSTEM_DISSONANCE]: SHOPIFY_CLIENT_ID missing from .env")
        return
    if not client_secret:
        print("[SYSTEM_DISSONANCE]: SHOPIFY_CLIENT_SECRET missing from .env")
        return

    token_url = f"https://{store_url}/admin/oauth/access_token"

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }

    print()
    print("=" * 60)
    print("--- [SHOPIFY_TOKEN_EXCHANGE] ---")
    print("=" * 60)
    print(f"\n  Store:  {store_url}")
    print(f"  Code:   {code[:12]}...")
    print()

    try:
        response = requests.post(token_url, json=payload)
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        scope = data.get("scope", "")

        if access_token:
            print("[SYSTEM_ECHO]: Token exchange SUCCESSFUL.\n")
            print(f"  Access Token: {access_token}")
            print(f"  Scope:        {scope}")
            print()
            print("  Add this to your .env file:")
            print(f"  SHOPIFY_ACCESS_TOKEN={access_token}")
            print()
            print("  NOTE: Shopify access tokens do not expire and are permanent")
            print("  until the app is uninstalled from the store.")
        else:
            print(f"[SYSTEM_DISSONANCE]: Unexpected response: {data}")

    except requests.exceptions.HTTPError as e:
        print(f"[SYSTEM_DISSONANCE]: Token exchange failed — {e}")
        print(f"  Response: {response.text}")
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Connection error — {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/shopify_exchange_code.py <AUTHORIZATION_CODE>")
        sys.exit(1)

    exchange_code(sys.argv[1])
