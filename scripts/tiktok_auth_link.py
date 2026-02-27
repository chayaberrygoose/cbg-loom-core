# [FILE_ID]: scripts/TIKTOK_AUTH_LINK // VERSION: 1.1 // STATUS: STABLE
# [NARRATIVE]: Generating the Authorization Link to extract the OAuth Code from the TikTok Archive.

import os
import urllib.parse
import secrets
from dotenv import load_dotenv

def generate_auth_url():
    load_dotenv()
    
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "https://localhost/")
    
    if not client_key:
        print("[SYSTEM_DISSONANCE]: TIKTOK_CLIENT_KEY missing from The Archive (.env).")
        return

    # Define the required scopes for Specimen transmission
    # TikTok v2 API requires space-separated scopes
    scopes = ["user.info.basic", "video.upload", "video.publish"]
    state = secrets.token_urlsafe(16)
    
    # Required Base URL
    base_url = "https://www.tiktok.com/v2/auth/authorize/"
    
    # Full Parameters
    params = {
        "client_key": client_key,
        "scope": " ".join(scopes),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state
    }
    
    # Diagnostic: Try the most basic scope first
    diagnostic_scopes = ["user.info.basic"]
    diagnostic_params = params.copy()
    diagnostic_params["scope"] = " ".join(diagnostic_scopes)
    
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    diagnostic_url = f"{base_url}?{urllib.parse.urlencode(diagnostic_params)}"
    
    print("\n" + "="*60)
    print("--- [TIKTOK_OAUTH_UPLINK]: DIAGNOSTIC MODE ---")
    print("="*60)
    print(f"\n[OPTION A]: FULL CONDUIT (Preferred)\n")
    print(auth_url)
    print(f"\n[OPTION B]: DIAGNOSTIC UPLINK (Basic info only - use if A fails 'client_key' error)\n")
    print(diagnostic_url)
    print(f"\n[VERIFICATION_REQUIRED]:")
    print(f"1. REDIRECT_URI: Ensure it exactly matches in the TikTok Portal: {redirect_uri}")
    print(f"2. CLIENT_KEY: Double check the key in .env matches the portal: {client_key}")
    print(f"3. TESTER STATUS: If your app is not 'Live', you MUST add your TikTok account as an 'Authorized Tester' in the portal.")
    print(f"4. SCOPES: Check if 'video.upload' is enabled for your app in the TikTok Developer console.")
    print("="*60 + "\n")

if __name__ == "__main__":
    generate_auth_url()
