# DotSense - Autonomous Braille Instruction System

DotSense is a desktop application plus Arduino-based tactile device designed to help users
practice Braille using vibration patterns and voice interaction.

## Screenshots
<img src="hardware/User Interface.jpeg" width = "180" alt="User Interface">
<img src="prototype_photo.jpeg" width = "180" alt = "Physical prototype">

## Repository Layout

- 'src/' - Python source code for the DotSense GUI and logic ('DotSense.py')
- 'arduino/' - Arduino sketch for controlling the vibration motors
- 'hardware/' - A photo, demo video, and notes about the physical prototype
- 'DotSense.exe' and '_internal/' - Windows build of the application
- 'palabras.txt' - Spanish word list used in training modes
- 'beep.wav' - Audio cue when the system is listening

## Pre-built Windows Application

To download the full Windows build (including 'DotSense.exe' and the '_internal/' folder),
use the following link:

> **Download (Windows build):** [Full DotSense Package](https://drive.google.com/drive/folders/1EQMhTGeYQZkoMqdyd7IHTFr3ZMV1HncU?usp=sharing)

## How to Run (Windows)
1. Ensure the Arduino is connected.
2. Upload 'arduino/braille_device.ino' to the device.
3. Double-click 'DotSense.exe'
4. Follow the on-screen or voice instructions.

> The Windows executable was built from a development snapshot of the project. The 'src/' folder
> contains the full source code corresponding to the same architecture and relevant features.

## Main Contributors

- **Emilio Daza (Dartmouth College)** - main software development (Python app, final Arduino sketch), interaction design.
- **Valeria Ruiz (Pontificia Universidad Católica del Perú - PUCP)** - mechatronics engineering student; design and construction of the physical vibration module.
- **Santiago Maza** - early prototype ideas which included code, and contributions to the physical design.

© 2025 Emilio Daza. All rights reserved.
Unauthorized commercial use is prohibited.
