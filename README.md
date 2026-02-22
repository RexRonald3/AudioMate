# 📖 Braille & Audio Reading Assistant (Prototype)

Welcome! This repository contains the code for an accessible, hardware-integrated reading assistant. The goal of this project is to help visually impaired individuals read printed text (like books or documents) and learn Braille independently, without needing a human mentor present.

The system acts as a bridge between the physical world and digital accessibility. It uses a webcam to "see" text, Python to "read" and process it, and an Arduino paired with servos to physically render the text into Braille, alongside audio feedback.



## 🧠 The Concept: Brain and Muscle

This project is split into two main parts that talk to each other constantly:

1. **The Brain (Python on a Laptop):** Handles the heavy lifting. It takes the picture, cleans it up, extracts the text using Optical Character Recognition (OCR), speaks out loud, and safely coordinates what happens next.
2. **The Muscle (Arduino Uno & Servos):** Listens for commands from the laptop. It takes specific letters, translates them into 6-dot Braille patterns, and physically moves the servos to raise or lower the pins.



## 🛠️ Measures to Take Before Running

To make this code work smoothly, you need to set up both the physical hardware and your software environment. Here is exactly what you need to do:

### 1. Hardware Setup

* **The Microcontroller:** An Arduino Uno connected to your laptop via USB.
* **The Servos:** 6 standard or micro servos connected to the Arduino's PWM pins (Pins 3, 5, 6, 9, 10, 11).
* **Power Warning:** Do *not* try to power 6 moving servos entirely through the Arduino's 5V USB connection. Use an external 5V power supply for the servos, and make sure the ground (GND) wire is shared with the Arduino.
* **The Camera:** A standard webcam positioned to look down at a piece of paper.

### 2. Software & Dependencies

You will need Python installed, along with a few specific libraries. Run this in your terminal:


pip install opencv-python pytesseract pyttsx3 pyserial numpy



### 3. The "Gotchas" (Crucial Code Adjustments)

Before you hit run, open the Python script and check these three things in the `CONFIG` section:

* **The Tesseract Engine:** You *must* install the actual Tesseract OCR software on your computer (it's not just a Python library). Once installed, update the `TESSERACT_CMD` path in the code to point to exactly where `tesseract.exe` lives on your machine.
* **The COM Port:** Find out which port your Arduino is plugged into (e.g., `COM3` on Windows or `/dev/ttyUSB0` on Mac/Linux) and update the `COM_PORT` variable.
* **The Camera Index:** If `CAMERA_INDEX = 0` opens your laptop's built-in webcam instead of your downward-facing document camera, change it to `1` or `2`.



## 📸 Under the Hood: Image Preprocessing

Cameras capture a lot of noise, shadows, and bad lighting. If we feed a raw image straight to the OCR engine, it will fail. To prevent this, the Python code runs the image through a quick "cleaning" pipeline using OpenCV:

1. **Grayscale Conversion:** We strip out all the color. The computer only cares about light and dark.
2. **Otsu's Thresholding:** This is the magic step. The code automatically calculates the perfect contrast point to force the background to turn pure white and the text to turn pure black, erasing shadows and making the letters pop.
3. **Space Stripping:** Once the text is extracted, the code removes weird line breaks and extra spaces so the audio engine doesn't sound like it's stuttering.



## 🎮 How to Use the System (The Controls)

The system is designed with a strict "State Machine" to prevent errors, meaning it will only listen to certain buttons at certain times.

* `C` **(Capture):** The only button that works when the system turns on. It takes a photo, processes the text, and unlocks the next steps. If it finds no text, it will announce an error and reset.
* `L` **(Learn Mode):** Spells out the captured text letter-by-letter. It sends a letter to the Arduino (raising the Braille pins), speaks the letter, waits for the user to feel it, and then lowers the pins before moving to the next one.
* `S` **(Speak Mode):** Bypasses the Arduino completely and just reads the captured text out loud as normal sentences.
* `X` **(Emergency Stop / Reset):** The ultimate override. No matter what the system is doing, pressing `X` instantly stops the audio, flushes the data cables, forces all servos back to zero degrees, and resets the system safely to the start.

