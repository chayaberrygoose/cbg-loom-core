import qrcode

# The Target: Our public heart and lore
REPO_URL = "https://github.com/chayaberrygoose/cbg-loom-core"
# The Destination: Local sync folder on the Raspberry Pi
OUTPUT_FILE = "repo_portal_qr.png"

def generate_portal():
    print(f"--- Generating QR Code for: {REPO_URL} ---")
    
    # Configure for high readability (Error Correction 'H' allows for some branding/dirt)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    qr.add_data(REPO_URL)
    qr.make(fit=True)

    # Create the image (Standard Black/White for 100% scan rate)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save it to the local filesystem
    img.save(OUTPUT_FILE)
    print(f"Success! Portal asset saved as: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_portal()
