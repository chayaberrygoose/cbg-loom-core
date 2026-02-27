# [FILE_ID]: scripts/PINTEREST_AUTH // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Generating the Authorization Link to extract the OAuth Code from the Pinterest Archive.

import os
import urllib.parse
import secrets
import requests
import base64
from dotenv import load_dotenv

def generate_auth_url():
    load_dotenv()
    
    client_id = os.getenv("PINTEREST_CLIENT_ID")
    redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "https://localhost/")
    
    if not client_id:
        print("[SYSTEM_DISSONANCE]: PINTEREST_CLIENT_ID missing from The Archive (.env).")
        return

    # Define the required scopes for Specimen pinning
    # Scopes: boards:read, boards:write, pins:read, pins:write
    scopes = ["boards:read", "boards:write", "pins:read", "pins:write", "user_accounts:read"]
    state = secrets.token_urlsafe(16)
    
    # Required Base URL
    base_url = "https://www.pinterest.com/oauth/"
    
    # Full Parameters
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(scopes),
        "state": state
    }
    
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    print("\n" + "="*60)
    print("--- [PINTEREST_OAUTH_UPLINK]: INITIATION ---")
    print("="*60)
    print(f"\n[STEP 1]: Navigate to the following URL in your browser:\n")
    print(auth_url)
    print(f"\n[STEP 2]: After authorizing, you will be redirected to your Redirect URI.")
    print("Copy the 'code' parameter from the URL.")
    print("\n[STEP 3]: Run this script again with the code to finalize the ritual.")
    print("Example: python scripts/pinterest_auth.py --code YOUR_CODE_HERE")

def exchange_code_for_token(code):
    load_dotenv()
    client_id = os.getenv("PINTEREST_CLIENT_ID")
    client_secret = os.getenv("PINTEREST_CLIENT_SECRET")
    redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "https://localhost/")

    if not all([client_id, client_secret]):
        print("[SYSTEM_DISSONANCE]: Credentials missing from The Archive.")
        return

    url = "https://api.pinterest.com/v5/oauth/token"
    
    # Pinterest requires Basic Auth header for token exchange
    auth_str = f"{client_id}:{client_secret}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        print("\n[SUCCESS]: Access Token acquired.")
        print(f"PINTEREST_ACCESS_TOKEN={access_token}")
        print("\n[ACTION]: Update your .env file with this token.")
    else:
        print(f"\n[FAILURE]: {response.status_code} - {response.text}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--code":
        exchange_code_for_token(sys.argv[2])
    else:
        generate_auth_url()
