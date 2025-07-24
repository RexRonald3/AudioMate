import pytesseract
import cv2
import pyttsx3
import time
import serial  # Import serial module
import numpy as np

# Initialize Serial Connection (Change 'COM3' to your actual port)
arduino = serial.Serial(port="COM1", baudrate=9600, timeout=1)
time.sleep(2)  # Allow time for connection

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 125)  # Adjust speech rate if needed

# Set path to Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Initialize webcam
webcam = cv2.VideoCapture(2)

def speak_text(text):
    """Function to speak text and wait until it's done."""
    engine.say(text)
    engine.runAndWait()  # This ensures the program waits for speech to finish

def preprocess_image(image_path):
    """Preprocess image by increasing contrast and sharpness."""
    img = cv2.imread(image_path)

    # Increase contrast using CLAHE (adaptive histogram equalization)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    contrast_enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # Sharpen the image using an unsharp mask
    gaussian = cv2.GaussianBlur(contrast_enhanced, (0, 0), 3)
    sharpened = cv2.addWeighted(contrast_enhanced, 1.5, gaussian, -0.5, 0)

    # Save and return processed image
    processed_path = "processed_image.jpg"
    cv2.imwrite(processed_path, sharpened)
    return processed_path

while True:
    try:
        # Capture frame from webcam
        check, frame = webcam.read()
        if not check:
            print("Failed to capture image from webcam.")
            break

        # Display the live video feed
        cv2.imshow("Capturing", frame)

        # Wait for user input
        key = cv2.waitKey(1)
        if key in [ord(' '), ord('x')]:  # ' ' (learn mode), 'x' (read mode)
            mode = "learn mode" if key == ord(' ') else "read mode"

            # Save the captured image
            image_path = 'savedimgg.jpg'
            cv2.imwrite(image_path, frame)
            print(f"Image captured and saved as '{image_path}'.")

            # Release the webcam
            webcam.release()

            # Preprocess the image
            processed_image_path = preprocess_image(image_path)

            # OCR Configuration (Improved settings)
            custom_config = r'--oem 3 --psm 6 -l eng'

            try:
                # Extract text from the processed image
                string = pytesseract.image_to_string(processed_image_path, config=custom_config)
                print("Extracted Text:", string)

                if string.strip():  # If text is not empty
                    cleaned_string = ' '.join(string.split())  # Remove extra spaces and newlines
                    print("Cleaned Text:", cleaned_string)

                    speak_text(f"Initiating {mode}")

                    if mode == "learn mode":
                        # Send characters to Arduino and speak them
                        for char in cleaned_string:
                            arduino.write(char.encode())  # Send character via Serial
                            print(f"Sent to Arduino: {char}")
                            speak_text(char)
                            time.sleep(0.1)  # Small delay

                    else:  # Read mode
                        speak_text(cleaned_string)

                else:
                    print("No text detected in the image.")
                    speak_text("No text detected.")

            except Exception as e:
                print(f"Error during text extraction: {e}")
                speak_text("Error extracting text.")

            # Close Serial Connection
            arduino.close()

            # Add a delay before closing the window
            time.sleep(2)

            # Close all OpenCV windows
            cv2.destroyAllWindows()
            break

    except KeyboardInterrupt:
        print("Turning off camera.")
        webcam.release()
        print("Camera off.")
        print("Program ended.")
        cv2.destroyAllWindows()
        arduino.close()
        break

# Release the webcam if not already released
if webcam.isOpened():
    webcam.release()
#rex #sabari