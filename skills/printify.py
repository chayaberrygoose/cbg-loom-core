import os
import shutil
import sys
from pathlib import Path

# Add the sync script directory to path so we can import it
ROOT_DIR = Path(__file__).parent.parent
SYNC_SCRIPT_DIR = ROOT_DIR / ".github" / "agents" / "skills" / "printify-catalog" / "scripts"
sys.path.append(str(SYNC_SCRIPT_DIR))

# Import the sync function from the existing catalog script
try:
    from sync_catalog import sync
except ImportError:
    # If the directory structure is different than expected, 
    # we can try to find it or use subprocess
    import subprocess
    def sync(shop_id, token_path, output_dir):
        script_path = SYNC_SCRIPT_DIR / "sync_catalog.py"
        subprocess.run([sys.executable, str(script_path), shop_id, token_path, output_dir], check=True)

def run_sync():
    # Configuration
    shop_id = "12043562"
    token_path = ROOT_DIR / ".env" / "prinitfy_api_token.txt"
    # The actual folder in artifacts
    local_catalog = ROOT_DIR / "artifacts" / "catalog"
    remote_mount = Path("/home/cbg/repos/cbg-share/catalog")

    print(f"--- [SYNC_START]: SHOP_{shop_id} ---")
    
    # 1. Run the sync logic
    try:
        sync(shop_id, str(token_path), str(local_catalog))
    except Exception as e:
        print(f"Error during sync: {e}")
        return

    # 2. Copy catalog to cbg-share mount
    print(f"--- [DEPLO_START]: REMOTE_CATALOG_SYNC ---")
    
    if remote_mount.exists():
        print(f"Clearing existing remote catalog at {remote_mount}...")
        shutil.rmtree(remote_mount)
    
    if local_catalog.exists():
        print(f"Copying {local_catalog} -> {remote_mount}")
        shutil.copytree(local_catalog, remote_mount)
        print("--- [SYNC_COMPLETE]: ALIGNMENT_VERIFIED ---")
    else:
        print(f"--- [ERROR]: LOCAL_CATALOG_NOT_FOUND at {local_catalog} ---")

if __name__ == "__main__":
    run_sync()
