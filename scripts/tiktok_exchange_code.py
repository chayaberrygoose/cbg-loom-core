# [FILE_ID]: scripts/TIKTOK_EXCHANGE_CODE // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Finalizing the OAuth Ritual by exchanging the Code for a User Access Token.

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

def exchange_code(code):
    load_dotenv()
    
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "https://localhost/")
    
    if not client_key or not client_secret:
        print("[SYSTEM_DISSONANCE]: Credentials missing from The Archive.")
        return

    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    }
    
    data = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    print(f"[SYSTEM_LOG]: Attempting token exchange for code: {code[:10]}...")
    
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            open_id = token_data.get("open_id")
            
            print("\n" + "="*60)
            print("--- [TIKTOK_RITUAL]: SUCCESS ---")
            print("="*60)
            print(f"ACCESS_TOKEN: {access_token}")
            print(f"OPEN_ID: {open_id}")
            print(f"EXPIRES_IN: {token_data.get('expires_in')} seconds")
            print("="*60)
            
            # Offer to save it
            repo_root = Path(__file__).parent.parent
            env_file = repo_root / ".env"
            
            print(f"\n[SYSTEM_LOG]: Appending ACCESS_TOKEN to {env_file}...")
            # We use a specific variable name the skill looks for
            with open(env_file, "a") as f:
                f.write(f"\nTIKTOK_ACCESS_TOKEN={access_token}\n")
            
            print("[SYSTEM_ECHO]: The Archive has been updated. TikTok Conduit is now RESONANT.")
            
        else:
            print(f"[SYSTEM_DISSONANCE]: Exchange failed. Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Ritual failure: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[SYSTEM_USAGE]: python3 scripts/tiktok_exchange_code.py <AUTHORIZATION_CODE_OR_URL>")
    else:
        target = sys.argv[1]
        # Check if the user pasted the whole URL instead of just the code
        if "code=" in target:
            import urllib.parse
            parsed = urllib.parse.urlparse(target)
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if code:
                print(f"[SYSTEM_LOG]: Code extracted from URL: {code[:10]}...")
                exchange_code(code)
            else:
                print("[SYSTEM_DISSONANCE]: No code found in that URL.")
        else:
            exchange_code(target)
