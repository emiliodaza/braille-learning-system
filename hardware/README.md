# DotSense - Hardware Prototype

This folder documents the physical prototype for the **DotSense** tactile Braille learning device.

## Overview

The prototype uses:
- Six vibration motors arranged in a 3x2 layout matching a Braille cell.
- An Arduino microcontroller that receives 6-bit Braille codes over serial communication.
- The sketch located in '../arduino/braille_device.ino' to active motors corresponding to the dots.

## Contents
- **prototype_photo.jpeg** - Photo of the assembled tactile module.
- **demo_video.mp4** - Demonstration (Spanish audio) showing the full system in operation.

## How to Use

1. Upload 'braille_device.ino' to an Arduino.
2. Connect the Arduino to the computer running 'DotSense.exe' or the Python program in '/src'.
3. Send a 6-character string such as '101010' over the serial port to activate corresponding motors.

## Main Contributors
- **Valeria Ruiz (PUCP)** - Electrical assembly of the tactitle module.
- **Emilio Daza (Dartmouth College)** - Software architecture, Python UI, Arduino firmware, system integration.
- **Santiago Maza** - Early prototype concepts, initial code and motor-control sketches.
