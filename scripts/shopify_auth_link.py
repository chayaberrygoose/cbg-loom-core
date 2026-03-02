# [FILE_ID]: scripts/SHOPIFY_AUTH_LINK // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Generates the Shopify OAuth authorization URL.
# Step 1 of 2 — open the printed URL in a browser, approve, then
# copy the `code` parameter from the redirect and feed it to
# scripts/shopify_exchange_code.py

import os
import secrets
import urllib.parse
from dotenv import load_dotenv


def generate_auth_url():
    load_dotenv()

    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    store_url = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")

    if not client_id:
        print("[SYSTEM_DISSONANCE]: SHOPIFY_CLIENT_ID missing from .env")
        return
    if not store_url:
        print("[SYSTEM_DISSONANCE]: SHOPIFY_STORE_URL missing from .env")
        return

    # Redirect URI — Shopify will send the auth code here.
    # For local dev, use a webhook catcher or localhost.
    redirect_uri = os.getenv(
        "SHOPIFY_REDIRECT_URI",
        "https://webhook.site/42d83608-ca0d-497e-b778-5cce66fbf3c7",
    )

    # Scopes needed for Blog + Products + Collections
    scopes = ",".join([
        "read_content",
        "write_content",
        "read_products",
        "write_products",
        "read_publications",
    ])

    nonce = secrets.token_urlsafe(16)

    params = {
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": nonce,
    }

    auth_url = f"https://{store_url}/admin/oauth/authorize?{urllib.parse.urlencode(params)}"

    print()
    print("=" * 60)
    print("--- [SHOPIFY_OAUTH_UPLINK] ---")
    print("=" * 60)
    print()
    print("Open this URL in a browser and approve the app:\n")
    print(auth_url)
    print()
    print("[NEXT_STEP]:")
    print("  After approving, you will be redirected.  Copy the `code`")
    print("  parameter from the URL and run:")
    print()
    print("    python3 scripts/shopify_exchange_code.py <CODE>")
    print()
    print(f"  Redirect URI configured: {redirect_uri}")
    print(f"  Store:                   {store_url}")
    print(f"  State / nonce:           {nonce}")
    print()


if __name__ == "__main__":
    generate_auth_url()
