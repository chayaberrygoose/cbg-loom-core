# [FILE_ID]: skills/PINTEREST_UPLINK // VERSION: 2.0 // STATUS: STABLE
# [NARRATIVE]: High-fidelity conduit to the Pinterest Archive for Specimen pinning.
# Uses Sandbox token for development; swap API base to production when ready.

import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class PinterestConduit:
    """
    The Ritual for transmitting Specimens to the Pinterest Archive.
    Handles Board creation, Pin orchestration, and connection verification.
    
    Sandbox mode uses: https://api-sandbox.pinterest.com/v5
    Production mode:   https://api.pinterest.com/v5
    """
    
    def __init__(self, sandbox=True):
        self.access_token = os.getenv("PINTEREST_ACCESS_TOKEN")
        self.sandbox = sandbox
        self.api_base_url = (
            "https://api-sandbox.pinterest.com/v5" if sandbox
            else "https://api.pinterest.com/v5"
        )
        self.headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
            "Content-Type": "application/json"
        }
        
        if not self.access_token:
            print("[SYSTEM_DISSONANCE]: PINTEREST_ACCESS_TOKEN not found in The Archive (.env).")

    # ── CONNECTION ──────────────────────────────────────────────
    
    def check_connection(self):
        """Verifies the uplink to Pinterest."""
        if not self.access_token:
            print("[SYSTEM_DISSONANCE]: No token available.")
            return False
            
        endpoint = f"{self.api_base_url}/user_account"
        try:
            response = requests.get(endpoint, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                username = data.get("username", "Unknown")
                print(f"[SYSTEM_ECHO]: Pinterest Uplink RESONANT. Signifier: @{username}")
                print(f"  Mode: {'SANDBOX' if self.sandbox else 'PRODUCTION'}")
                print(f"  Account Type: {data.get('account_type', 'N/A')}")
                return True
            else:
                print(f"[SYSTEM_DISSONANCE]: Uplink failed. Code: {response.status_code}")
                print(f"  Response: {response.text}")
                return False
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: Connection Ritual failed: {e}")
            return False

    # ── BOARDS ──────────────────────────────────────────────────
    
    def list_boards(self):
        """Lists all boards in the Pinterest Archive."""
        endpoint = f"{self.api_base_url}/boards"
        try:
            response = requests.get(endpoint, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                boards = data.get("items", [])
                print(f"[SYSTEM_ECHO]: {len(boards)} board(s) detected in Archive.")
                for b in boards:
                    print(f"  [{b.get('id')}] {b.get('name')} — {b.get('description', 'No description')}")
                return boards
            else:
                print(f"[SYSTEM_DISSONANCE]: Board scan failed: {response.status_code} — {response.text}")
                return []
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: {e}")
            return []

    def create_board(self, name, description="Specimens from the Loom."):
        """Creates a new board in the Pinterest Archive."""
        endpoint = f"{self.api_base_url}/boards"
        payload = {
            "name": name,
            "description": description,
            "privacy": "PUBLIC"
        }
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            if response.status_code in [200, 201]:
                data = response.json()
                board_id = data.get("id")
                print(f"[SYSTEM_ECHO]: Board created. ID: {board_id} — Name: {name}")
                return data
            else:
                print(f"[SYSTEM_DISSONANCE]: Board creation failed: {response.status_code} — {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: {e}")
            return None

    # ── PINS ────────────────────────────────────────────────────
    
    def create_pin(self, board_id, title, description, image_url=None, image_path=None, link=None):
        """
        Creates a pin on a specified board.
        Supports image_url (remote) or image_path (local upload via media).
        """
        endpoint = f"{self.api_base_url}/pins"
        
        payload = {
            "board_id": board_id,
            "title": title,
            "description": description,
        }
        
        if link:
            payload["link"] = link
        
        if image_url:
            payload["media_source"] = {
                "source_type": "image_url",
                "url": image_url
            }
        elif image_path:
            # Upload media first, then reference it
            media_id = self._upload_media(image_path)
            if media_id:
                payload["media_source"] = {
                    "source_type": "media_id",
                    "media_id": media_id
                }
            else:
                print("[SYSTEM_DISSONANCE]: Media upload failed. Aborting pin creation.")
                return None
        else:
            print("[SYSTEM_DISSONANCE]: No image source provided for pin.")
            return None
        
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            if response.status_code in [200, 201]:
                data = response.json()
                pin_id = data.get("id")
                print(f"[SYSTEM_ECHO]: Pin created. ID: {pin_id} — Title: {title}")
                return data
            else:
                print(f"[SYSTEM_DISSONANCE]: Pin creation failed: {response.status_code} — {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: {e}")
            return None

    def _upload_media(self, image_path):
        """Registers a media upload and streams the file."""
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"[SYSTEM_DISSONANCE]: Specimen not found: {image_path}")
            return None
        
        # Step 1: Register the media upload
        endpoint = f"{self.api_base_url}/media"
        register_payload = {"media_type": "image"}
        
        try:
            response = requests.post(endpoint, headers=self.headers, json=register_payload)
            if response.status_code in [200, 201]:
                data = response.json()
                media_id = data.get("media_id")
                upload_url = data.get("upload_url")
                upload_params = data.get("upload_parameters", {})
                
                print(f"[SYSTEM_LOG]: Media registered. ID: {media_id}")
                
                # Step 2: Upload the file to the provided URL
                with open(image_path, "rb") as f:
                    files = {"file": (image_path.name, f)}
                    upload_response = requests.post(
                        upload_url,
                        data=upload_params,
                        files=files
                    )
                
                if upload_response.status_code in [200, 201, 204]:
                    print(f"[SYSTEM_ECHO]: Media uploaded successfully.")
                    return media_id
                else:
                    print(f"[SYSTEM_DISSONANCE]: Upload stream failed: {upload_response.status_code}")
                    return None
            else:
                print(f"[SYSTEM_DISSONANCE]: Media registration failed: {response.status_code} — {response.text}")
                return None
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: {e}")
            return None

    def list_pins(self, board_id):
        """Lists all pins on a board."""
        endpoint = f"{self.api_base_url}/boards/{board_id}/pins"
        try:
            response = requests.get(endpoint, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                pins = data.get("items", [])
                print(f"[SYSTEM_ECHO]: {len(pins)} pin(s) on board {board_id}.")
                for p in pins:
                    print(f"  [{p.get('id')}] {p.get('title', 'Untitled')}")
                return pins
            else:
                print(f"[SYSTEM_DISSONANCE]: Pin list failed: {response.status_code} — {response.text}")
                return []
        except Exception as e:
            print(f"[SYSTEM_DISSONANCE]: {e}")
            return []


def main():
    import sys
    conduit = PinterestConduit(sandbox=True)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--verify":
            conduit.check_connection()
        elif cmd == "--boards":
            conduit.list_boards()
        elif cmd == "--create-board" and len(sys.argv) > 2:
            conduit.create_board(sys.argv[2])
        else:
            print("[SYSTEM_USAGE]:")
            print("  --verify           Check connection")
            print("  --boards           List all boards")
            print("  --create-board NAME  Create a new board")
    else:
        conduit.check_connection()

if __name__ == "__main__":
    main()
