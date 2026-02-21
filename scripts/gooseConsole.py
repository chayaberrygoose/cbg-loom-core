import time
import os
import sys

# ASCII Art Frames for the Rotation
f1 = r"""
     __
   /(  )>
  |  /
   ww
"""
f2 = r"""
      __
     (  \__
      \  _ \
       ww  \\
"""
f3 = r"""
     __
    <  )\
      \  |
       ww
"""
f4 = r"""
        __
     __/  )
    / _  /
   //  ww
"""

frames = [f1, f2, f3, f4]

def draw_speech_bubble(message):
    length = len(message) + 2
    bubble =  f"   +{'-' * length}+\n"
    bubble += f"   | {message} |\n"
    bubble += f"   +{'-' * length}+\n"
    bubble += "    \\"
    return bubble

def finite_goose(message_file):
    # Default messages if file is missing or empty
    default_messages = [
        "waiting for connection...",
        "signal detected...",
        "data stream active...",
        "waiting for loom..."
    ]
    
    messages = []
    if os.path.exists(message_file):
        with open(message_file, 'r') as f:
            messages = [line.strip() for line in f if line.strip()]
    
    # Use defaults if file-based messages list is empty
    if not messages:
        messages = default_messages

    try:
        # Loop through each message exactly once
        for current_msg in messages:
            start_time = time.time()
            
            # Rotate for 4 seconds per message
            while time.time() - start_time < 4:
                for frame in frames:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                    print("\n" * 3)
                    print(draw_speech_bubble(current_msg))
                    print(frame)
                    print("\n" * 2)
                    
                    time.sleep(0.2) # Rotation speed
                    
                    if time.time() - start_time >= 4:
                        break

        print("\n--- Sequence Complete. Honk! ---")
                
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    finite_goose("messages.txt")
