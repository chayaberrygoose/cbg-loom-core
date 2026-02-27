# [FILE_ID]: skills/TIKTOK_CONDUIT // VERSION: 1.0 // STATUS: UNSTABLE
# [NARRATIVE]: Establishing a high-fidelity uplink to the TikTok Archive for Specimen transmission.

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Initialize environment
load_dotenv()

class TikTokConduit:
    """
    The Ritual for transmitting Specimens to the TikTok Archive.
    Handles authentication and Direct Post protocols.
    """
    
    def __init__(self):
        self.client_key = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
        self.access_token = self._fetch_credential()
        self.api_base_url = "https://open.tiktokapis.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
    def _fetch_credential(self):
        """
        Retrieves the access token from the local environment or secret store.
        If Client Key/Secret are present, attempts to negotiate a Client Access Token.
        """
        token = os.getenv("TIKTOK_ACCESS_TOKEN")
        
        if not token:
            # Fallback path logic
            try:
                current_dir = Path(__file__).parent.absolute()
                repo_root = current_dir.parent.parent.parent
                token_path = repo_root / ".env" / "tiktok_access_token.txt"
                
                if token_path.exists():
                    token = token_path.read_text().strip()
            except Exception:
                pass

        if not token and self.client_key and self.client_secret:
            print("[SYSTEM_LOG]: Attempting Client Credential Ritual...")
            token = self._negotiate_client_token()
                
        if not token:
            print("[SYSTEM_DISSONANCE]: TIKTOK_ACCESS_TOKEN not found in The Archive.")
            return None
            
        return token

    def _negotiate_client_token(self):
        """
        Exchanges Client Key/Secret for an Ephemeral Access Token.
        """
        url = "https://open.tiktokapis.com/v2/oauth/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                token_data = response.json()
                print("[SYSTEM_ECHO]: Client Access Token retrieved.")
                return token_data.get("access_token")
            else:
                print(f"[SYSTEM_DISSONANCE]: Ritual failed: {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Negotiation error: {e}")
            return None

    def check_connection(self):
        """
        Verifies the uplink to TikTok.
        If using a Client Token, it confirms validity of credentials.
        """
        if not self.access_token:
            print("[SYSTEM_DISSONANCE]: No token available for verification.")
            return False
            
        print(f"[SYSTEM_LOG]: Token prefix: {self.access_token[:5]}...")
        
        # Try user info - will fail for client tokens but succeed for user tokens
        url = f"{self.api_base_url}/user/info/"
        params = {"fields": "display_name,username"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                data = response.json()
                signifier = data.get('data', {}).get('user', {}).get('display_name', 'Unknown')
                print(f"[SYSTEM_ECHO]: User Uplink established. Signifier: {signifier}")
                return True
            elif response.status_code == 401 and self.access_token.startswith("clt"):
                print("[SYSTEM_ECHO]: Client Credentials Verified. (Client tokens cannot access User Info).")
                print("[SYSTEM_LOG]: Uplink to Commercial Conduit status: RESONANT.")
                return True
            else:
                print(f"[SYSTEM_DISSONANCE]: Uplink failed. Code: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Connection Ritual failed: {e}")
            return False

    def post_video(self, video_path, title, privacy_level="PUBLIC_TO_EVERYONE"):
        """
        Initiates the Direct Post ritual for a video Specimen.
        Note: This is a multi-step process involving initialization and file streaming.
        """
        if not self.access_token:
            print("[SYSTEM_DISSONANCE]: Cannot transmit without valid credentials.")
            return None

        video_path = Path(video_path)
        if not video_path.exists():
            print(f"[SYSTEM_DISSONANCE]: Specimen not found at {video_path}")
            return None

        print(f"[SYSTEM_LOG]: Preparing transmission of Specimen: {video_path.name}")
        
        # 1. Initialize Post Ritual
        init_url = f"{self.api_base_url}/post/publish/video/init/"
        # Simplistic payload for demonstration; real API needs exact file size etc.
        payload = {
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_ad_tag": False
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_path.stat().st_size,
                "chunk_size": video_path.stat().st_size,
                "total_chunk_count": 1
            }
        }

        try:
            response = requests.post(init_url, headers=self.headers, json=payload)
            if response.status_code == 200:
                data = response.json().get('data', {})
                publish_id = data.get('publish_id')
                upload_url = data.get('upload_url')
                print(f"[SYSTEM_ECHO]: Ritual Initialized. Publish ID: {publish_id}")
                
                if upload_url:
                    return self._stream_specimen(video_path, upload_url, publish_id)
                return publish_id
            else:
                print(f"[SYSTEM_DISSONANCE]: Initialization failed: {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Transmission init failed: {e}")
            return None

    def _stream_specimen(self, file_path, upload_url, publish_id):
        """
        Streams the file bytes to the negotiated upload URL.
        """
        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"
        }
        
        print(f"[SYSTEM_LOG]: Streaming bytes to TikTok Archive...")
        try:
            with open(file_path, 'rb') as f:
                response = requests.put(upload_url, headers=headers, data=f)
                
            if response.status_code in [200, 201]:
                print(f"[SYSTEM_ECHO]: Transmission complete for {publish_id}.")
                return publish_id
            else:
                print(f"[SYSTEM_DISSONANCE]: Streaming failed. Code: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Critical error during streaming: {e}")
            return None

def main():
    conduit = TikTokConduit()
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        conduit.check_connection()
    else:
        print("[SYSTEM_LOG]: TikTok Conduit Skill loaded. Use '--verify' to check status.")

if __name__ == "__main__":
    main()
