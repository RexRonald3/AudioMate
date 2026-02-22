import cv2
import pytesseract
import pyttsx3
import serial
import time
import numpy as np
import threading

# =================CONFIG=================
# CHANGE THESE TO MATCH YOUR SETUP
COM_PORT = 'COM3'  # e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux
BAUD_RATE = 115200 # Must match Arduino
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
CAMERA_INDEX = 0   # Usually 0 for built-in, 1 or 2 for external

# Initialize Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Initialize TTS
engine = pyttsx3.init()
engine.setProperty('rate', 150)

# State Machine Variables
# States: "IDLE", "CAPTURED_WAITING", "BUSY_LEARNING", "BUSY_SPEAKING"
system_state = "IDLE"
extracted_text_clean = ""
stop_signal = False # Flag to interrupt long-running loops

# =================HARDWARE HANDLES=================
arduino = None
webcam = None

# =================HELPER FUNCTIONS=================

def speak_text(text, blocking=True):
    """Speaking helper function."""
    print(f"[AUDIO OUT]: {text}")
    # IMPORTANT: If X is pressed, we shouldn't queue more audio
    if stop_signal and system_state == "IDLE": return

    engine.say(text)
    if blocking:
        engine.runAndWait()
    else:
        # For non-blocking audio (advanced), requires different engine handling.
        # Sticking to blocking for reliability in prototype.
        engine.runAndWait() 

def connect_arduino():
    global arduino
    try:
        arduino = serial.Serial(port=COM_PORT, baudrate=BAUD_RATE, timeout=2)
        time.sleep(3) # Wait for Arduino reboot
        print("Arduino connected.")
        # Flush initial garbage data
        arduino.reset_input_buffer()
        return True
    except Exception as e:
        print(f"Arduino connection failed: {e}")
        speak_text("Error. Hardware connection failed.")
        return False

def send_arduino_command_wait_ack(command_str, timeout=5):
    """Sends a command <CMD> and waits for <ACK_...> response."""
    global arduino, stop_signal
    if not arduino or not arduino.is_open: return False
    
    # Wrap command in start/end markers
    full_cmd = f"<{command_str}>"
    arduino.write(full_cmd.encode())
    # print(f"Sent to Arduino: {full_cmd}") # Debug

    start_time = time.time()
    received_ack = ""
    
    while (time.time() - start_time) < timeout:
        # CRITICAL SAFETY CHECK DURING WAIT PERIOD
        if stop_signal: return False

        if arduino.in_waiting > 0:
            try:
                # Read until newline, decode, strip whitespace
                line = arduino.read_until().decode('utf-8').strip()
                if line.startswith("<ACK_") and line.endswith(">"):
                    # print(f"Arduino ACK received: {line}") # Debug
                    return True
            except:
               pass # Ignore decoding errors in serial noise
        time.sleep(0.05)
        
    print("Error: Arduino timed out waiting for ACK.")
    return False

def safe_reset_system():
    """The 'X' Button Handler. Stops everything, resets hardware."""
    global system_state, stop_signal, extracted_text_clean
    print("\n--- INITIATING SAFE RESET ---")
    stop_signal = True # Signal any running loops to break
    system_state = "IDLE"
    extracted_text_clean = ""
    
    speak_text("Halting system. Resetting to start.", blocking=True)
    
    # Send physical reset signal to servos
    if arduino and arduino.is_open:
        # Clear serial buffers first
        arduino.reset_input_buffer()
        arduino.reset_output_buffer()
        # Send reset command multiple times to ensure reception during chaos
        for _ in range(3):
             arduino.write(b"<RESET>")
             time.sleep(0.1)
        print("Sent hardware reset signal.")
    
    # Reset stop signal so we can start again
    stop_signal = False 
    speak_text("System Ready. Press C to capture.")
    print("--- RESET COMPLETE. State: IDLE ---\n")

# =================CORE LOGIC MODES=================

def preprocess_and_extract(image_frame):
    """Basic image cleanup and OCR."""
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    # Apply simple thresholding to contrast black text on white paper
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    custom_config = r'--oem 3 --psm 6 -l eng'
    text = pytesseract.image_to_string(thresh, config=custom_config)
    
    # Clean text: keep letters, numbers, basic punctuation, and spaces between words.
    # Replace newlines with spaces to treat it as one continuous line.
    cleaned = " ".join(text.splitlines())
    # Remove excessive internal spaces
    cleaned = " ".join(cleaned.split())
    return cleaned

def run_learn_mode_loop(text_to_learn):
    """Iterates through text, sends to Arduino, waits for handshake."""
    global system_state, stop_signal
    system_state = "BUSY_LEARNING"
    
    speak_text("Starting Learn Mode. Hands on device.")
    
    # Initial safety reset before starting
    if stop_signal: return
    if not send_arduino_command_wait_ack("RESET"):
        speak_text("Hardware communication error.")
        safe_reset_system()
        return

    words = text_to_learn.split(' ')
    
    for word in words:
        if stop_signal: break # Immediate Exit check
        
        for char in word:
            if stop_signal: break # Immediate Exit check

            # 1. If it's a letter, send to Arduino to raise pins
            if char.isalpha():
                # Send char and wait for ACK that pins are UP
                if not send_arduino_command_wait_ack(char):
                     speak_text("Hardware error during process.") break

            # 2. Audio feedback
            speak_text(char.lower(), blocking=True)
            
            if stop_signal: break # Exit check post-audio

            # 3. Short delay for user to feel it
            time.sleep(0.5) 

            # 4. Send RESET to lower pins and wait for ACK
            if not send_arduino_command_wait_ack("RESET"): break
            
            # 5. Short delay before next character
            time.sleep(0.2)

        # Small pause between words
        time.sleep(0.5)

    # Loop finished naturally or broken via stop_signal
    if not stop_signal:
        speak_text("Learning complete.")
        safe_reset_system()
    else:
        # If stop_signal was true, the main loop handles calling safe_reset_system
        print("Learn mode interrupted by X.")


# =================MAIN EXECUTION=================

def main():
    global system_state, extracted_text_clean, webcam, stop_signal

    # Initial Hardware Setup
    speak_text("Initializing hardware. Please wait.")
    if not connect_arduino():
        speak_text("Critical hardware failure. Exiting.")
        return

    webcam = cv2.VideoCapture(CAMERA_INDEX)
    if not webcam.isOpened():
        speak_text("Camera not found. Exiting.")
        return

    # Initial system state confirmation
    safe_reset_system() 

    while True:
        # 1. Capture Live Frame needed for cv2.waitKey loop
        ret, frame = webcam.read()
        if not ret:
            print("Webcam failure")
            break
        
        # Display current state on screen for debugging
        cv2.putText(frame, f"State: {system_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Braille Assistant Prototype", frame)

        # 2. Key Input Handler (1ms delay)
        key = cv2.waitKey(1) & 0xFF

        # --- GLOBAL INTERRUPT 'X' ---
        # This is the highest priority check.
        if key == ord('x'):
            if system_state != "IDLE":
                 # If busy, flag the stop signal, the busy loop will detect it and exit
                 stop_signal = True
                 # Give the busy loop a moment to detect the flag and stop
                 time.sleep(0.5) 
                 safe_reset_system()
            else:
                 # If already idle, just ensure everything is clean
                 safe_reset_system()
            continue # Skip the rest of loop logic

        # --- STATE: IDLE (Only accepts 'C') ---
        if system_state == "IDLE":
            if key == ord('c'):
                speak_text("Capturing image. Processing.")
                extracted_text_clean = preprocess_and_extract(frame)
                print(f"Extracted: '{extracted_text_clean}'")

                # .strip() ensures we don't accidentally accept a string of empty spaces
                if len(extracted_text_clean.strip()) > 0:
                    system_state = "CAPTURED_WAITING"
                    speak_text("Capture successful. Press L for Learn Mode, or S for Speak Mode.")
                else:
                    # NEW LOGIC: OCR Failed
                    print("OCR Error: No readable text found.")
                    speak_text("Text extraction failed.")
                    
                    # Force the system back to the absolute starting point
                    safe_reset_system()
                    # Stay in IDLE state

        # --- STATE: CAPTURED_WAITING (Accepts 'L' or 'S') ---
        elif system_state == "CAPTURED_WAITING":
            if key == ord('s'):
                system_state = "BUSY_SPEAKING"
                # Ensure servos are down before speaking
                send_arduino_command_wait_ack("RESET")
                speak_text(extracted_text_clean, blocking=True)
                safe_reset_system() # Done speaking, return to start

            elif key == ord('l'):
                 # We launch learning in a separate thread so the main loop
                 # keeps running to detect the 'X' key press in cv2.waitKey
                 learn_thread = threading.Thread(target=run_learn_mode_loop, args=(extracted_text_clean,))
                 learn_thread.daemon = True # Ensure thread dies if main program dies
                 learn_thread.start()
                 # system_state is updated to BUSY_LEARNING inside the thread function

        # --- STATES: BUSY (Ignore other keys except X) ---
        # If state is BUSY_LEARNING or BUSY_SPEAKING, we ignore C, L, S.
        # The 'X' check at the top handles interruptions.
        pass

    # Cleanup on exit
    webcam.release()
    cv2.destroyAllWindows()
    if arduino: arduino.close()

if __name__ == "__main__":
    main()
