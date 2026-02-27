# [FILE_ID]: scripts/TIKTOK_AUTH_LINK // VERSION: 2.1 // STATUS: STABLE
# [NARRATIVE]: Generating the Authorization Link for Web OAuth from the TikTok Archive.

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

    # TikTok v2 API requires COMMA-separated scopes (not spaces)
    scopes = ["user.info.basic", "video.upload", "video.publish"]
    state = secrets.token_urlsafe(16)
    
    base_url = "https://www.tiktok.com/v2/auth/authorize/"
    
    params = {
        "client_key": client_key,
        "scope": ",".join(scopes),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state
    }
    
    # Diagnostic: Minimal scope variant
    diagnostic_params = params.copy()
    diagnostic_params["scope"] = "user.info.basic"
    
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    diagnostic_url = f"{base_url}?{urllib.parse.urlencode(diagnostic_params)}"
    
    print("\n" + "="*60)
    print("--- [TIKTOK_OAUTH_UPLINK]: WEB MODE ---")
    print("="*60)
    print(f"\n[OPTION A]: FULL CONDUIT (Preferred)\n")
    print(auth_url)
    print(f"\n[OPTION B]: DIAGNOSTIC UPLINK (Basic info only)\n")
    print(diagnostic_url)
    print(f"\n[VERIFICATION_REQUIRED]:")
    print(f"1. REDIRECT_URI must exactly match portal: {redirect_uri}")
    print(f"2. CLIENT_KEY in portal: {client_key}")
    print(f"3. App type must be set to 'Web' (not Desktop).")
    print(f"4. If app is in Staging, add your TikTok account as an Authorized Tester.")
    print(f"5. Scopes 'video.upload' and 'video.publish' must be enabled in Products.")
    print("="*60 + "\n")

if __name__ == "__main__":
    generate_auth_url()
