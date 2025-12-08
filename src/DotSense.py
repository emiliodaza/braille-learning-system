import tkinter as tk
from tkinter import messagebox, font
import serial
import time
import random
import threading
import speech_recognition as sr
from gtts import gTTS
import os
import pygame
import uuid
from PIL import Image, ImageDraw
import serial.tools.list_ports
import difflib

# Braille mapping
BRAILLE_MAPPING = {
    "A": "100000",
    "B": "110000",
    "C": "100100",
    "D": "100110",
    "E": "100010",
    "F": "110100",
    "G": "110110",
    "H": "110010",
    "I": "010100",
    "J": "010110",
    "K": "101000",
    "L": "111000",
    "M": "101100",
    "N": "101110",
    "O": "101010",
    "P": "111100",
    "Q": "111110",
    "R": "111010",
    "S": "011100",
    "T": "011110",
    "U": "101001",
    "V": "111001",
    "X": "101101",
    "Y": "101111",
    "Z": "101011",
    "Á": "011001",
    "É": "011111",
    "Ú": "110111",
    "Ñ": "110011",
    "Ü": "010111",
    "W": "001100",
    "Í": "001101",
}
WORDS_FILENAME = "palabras.txt"

pygame.mixer.init()
words_list = []
ser = None
recognizer = sr.Recognizer()

# Updated recognizer settings for better and faster voice input.
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 150      # Lowered from 300
recognizer.pause_threshold = 0.5         # Lowered from 0.8
recognizer.non_speaking_duration = 0.3   # Lowered from 0.5

# Global variables for training
training_mode = None
training_running = False
cancel_exercise_event = threading.Event()  # Signals cancellation of current exercise or speech
training_thread = None  # Holds the training thread

# For LETRAS mode: Exclude accented letters.
ACCENTED_LETTERS = {"Á", "É", "Ú", "Í", "Ü"}
SPECIAL_LETTERS = {"Ñ"}
ALLOWED_LETTERS = list(set(BRAILLE_MAPPING.keys()) - ACCENTED_LETTERS)

def cancel_current_speech():
    """Immediately stop any speech playback."""
    pygame.mixer.music.stop()

def speak(text):
    temp_filename = f"temp_{uuid.uuid4().hex}.mp3"
    try:
        tts = gTTS(text=text, lang="es")
        tts.save(temp_filename)
        pygame.mixer.music.load(temp_filename)
        pygame.mixer.music.play()
        # Check for cancellation during playback.
        while pygame.mixer.music.get_busy():
            if cancel_exercise_event.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.1)
        pygame.mixer.music.unload()
        time.sleep(0.2)
    except Exception as e:
        print("Error en TTS:", e)
    finally:
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except Exception as e:
            print("Error al eliminar el archivo temporal:", e)

def play_listening_sound():
    try:
        sound = pygame.mixer.Sound("beep.wav")
        sound.play()
    except Exception as e:
        print("Error al reproducir el sonido de escucha:", e)

def listen_for_speech(timeout=10, phrase_time_limit=5):  # Increased phrase_time_limit to 5 seconds
    with sr.Microphone() as source:
        # Increase calibration time to 2 seconds for better ambient noise adjustment.
        recognizer.adjust_for_ambient_noise(source, duration=2)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            text = recognizer.recognize_google(audio, language="es-ES")
            log_message("Texto reconocido: " + text)  # Debug log for recognized text
            return text.strip().upper()
        except sr.WaitTimeoutError:
            print("No se detectó voz.")
        except sr.UnknownValueError:
            print("No se pudo entender el audio.")
        except sr.RequestError as e:
            print("Error de reconocimiento de voz; verifique la conexión a internet.", e)
    return None

def get_speech_with_retry(prompt, retry_prompt, max_retries=10, timeout=10, phrase_time_limit=5):
    if cancel_exercise_event.is_set():
        return "CANCELLED"
    speak(prompt)
    time.sleep(0.3)
    log_message("Escuchándote...")
    play_listening_sound()
    respuesta = listen_for_speech(timeout=timeout, phrase_time_limit=phrase_time_limit)
    if cancel_exercise_event.is_set():
        return "CANCELLED"
    retry_count = 0
    while respuesta is None and retry_count < max_retries:
        if cancel_exercise_event.is_set():
            return "CANCELLED"
        speak(retry_prompt)
        time.sleep(0.3)
        log_message("No se ha detectado respuesta. Escuchándote nuevamente...")
        play_listening_sound()
        respuesta = listen_for_speech(timeout=timeout, phrase_time_limit=phrase_time_limit)
        retry_count += 1
    return respuesta

def send_braille_code(code):
    if ser and ser.is_open:
        try:
            # Append a newline so the Arduino can read a full 6-character code
            ser.write((code + "\n").encode())
            print("Enviado a Arduino:", code)
        except Exception as e:
            print("Error al enviar a Arduino:", e)
    else:
        print("Puerto serie no abierto. Código:", code)


def process_word(word):
    # Check for cancellation before and during the exercise.
    for letter in word:
        if cancel_exercise_event.is_set():
            return
        braille_code = BRAILLE_MAPPING.get(letter, "000000")
        send_braille_code(braille_code)
        time.sleep(0.5)
    time.sleep(1)

def training_loop():
    global training_running, training_mode
    while training_running:
        if cancel_exercise_event.is_set():
            break  # Stop loop immediately if cancellation is signaled.
        if training_mode in ["PALABRAS", "PALABRA"]:
            random_word = random.choice(words_list).strip().upper()
            log_message("Palabra seleccionada (para vibrar): " + random_word)
            process_word(random_word)
            respuesta = get_speech_with_retry("Diga la palabra que sintió.", "No se ha detectado respuesta. Por favor, repita la palabra.")
            if respuesta == "CANCELLED":
                break
            if respuesta:
                if respuesta == random_word:
                    speak("Correcto")
                    log_message("Respuesta correcta: " + respuesta)
                    update_status("✓ Correcto: " + respuesta, "success")
                else:
                    speak("Incorrecto, la palabra era " + random_word)
                    log_message("Respuesta incorrecta: " + respuesta + ". Debía ser: " + random_word)
                    update_status("✗ Incorrecto: " + respuesta + " → " + random_word, "error")
            else:
                speak("No se recibió respuesta.")
                log_message("No se recibió respuesta.")
                update_status("No se recibió respuesta", "warning")
        elif training_mode in ["LETRAS", "LETRA"]:
            random_letter = random.choice(ALLOWED_LETTERS)
            log_message("Letra seleccionada (para vibrar): " + random_letter)
            send_braille_code(BRAILLE_MAPPING[random_letter])
            time.sleep(1)
            if random_letter in SPECIAL_LETTERS:
                prompt_text = "Diga una palabra que contenga la letra " + random_letter
            else:
                prompt_text = "Diga una palabra que comience con la letra que sintió"
            respuesta = get_speech_with_retry(prompt_text, "No se ha detectado respuesta. Por favor, repita la palabra.")
            if respuesta == "CANCELLED":
                break
            if respuesta:
                if random_letter in SPECIAL_LETTERS:
                    if random_letter in respuesta:
                        speak("Correcto")
                        log_message("Respuesta correcta: " + respuesta)
                        update_status("✓ Correcto: " + respuesta, "success")
                    else:
                        speak("Incorrecto, la letra era " + random_letter)
                        log_message("Respuesta incorrecta: " + respuesta + ". Debía contener: " + random_letter)
                        update_status("✗ Incorrecto: " + respuesta + " → " + random_letter, "error")
                else:
                    words_in_response = respuesta.split()
                    first_word = words_in_response[0] if words_in_response else ""
                    if first_word and first_word[0] == random_letter:
                        speak("Correcto")
                        log_message("Respuesta correcta: " + first_word)
                        update_status("✓ Correcto: " + first_word, "success")
                    else:
                        speak("Incorrecto, la letra era " + random_letter)
                        log_message("Respuesta incorrecta: " + first_word + ". Debía comenzar con: " + random_letter)
                        update_status("✗ Incorrecto: " + first_word + " → " + random_letter, "error")
            else:
                speak("No se recibió respuesta.")
                log_message("No se recibió respuesta.")
                update_status("No se recibió respuesta", "warning")
        time.sleep(1)

def start_training():
    global training_mode, training_running, training_thread
    # Cancel any ongoing training session and wait for it to finish.
    if training_running:
        training_running = False
        cancel_exercise_event.set()
        log_message("Cambiando el modo del entrenamiento...")
        if training_thread is not None:
            training_thread.join()
        cancel_exercise_event.clear()
    # Mode selection loop.
    mode = None
    expected_modes = ["PALABRAS", "LETRAS"]
    while mode is None:
        mode_recognized = get_speech_with_retry(
            "Indique el modo de entrenamiento: palabras o letras",
            "Por favor, indique el modo de entrenamiento nuevamente.",
            max_retries=3
        )
        log_message("Modo reconocido: " + str(mode_recognized))
        if mode_recognized:
            # Use difflib to find the closest match.
            match = difflib.get_close_matches(mode_recognized, expected_modes, n=1, cutoff=0.6)
            if match:
                mode = match[0]
            else:
                speak("Modo no reconocido. Por favor, indique el modo de entrenamiento: palabras o letras.")
                log_message("Modo no reconocido: " + mode_recognized)
                time.sleep(0.3)
        else:
            speak("No se recibió respuesta para el modo de entrenamiento. Por favor, intente de nuevo.")
            log_message("No se recibió respuesta para el modo de entrenamiento.")
            time.sleep(0.3)
    training_mode = mode
    training_running = True
    speak("Entrenamiento iniciado en modo " + training_mode.lower())
    update_training_status(True, training_mode)
    log_message("Entrenamiento iniciado en modo " + training_mode)
    training_thread = threading.Thread(target=training_loop, daemon=True)
    training_thread.start()

def init_serial():
    global ser
    available_ports = list(serial.tools.list_ports.comports())
    arduino_port = None

    # Search for a port explicitly identified as Arduino.
    for port in available_ports:
        if "Arduino" in port.description:
            arduino_port = port.device
            break

    if arduino_port:
        try:
            ser = serial.Serial(arduino_port, 9600, timeout=1)
            speak("Conexión establecida con el dispositivo Arduino en el puerto " + arduino_port)
            log_message("Conexión serial establecida en " + arduino_port)
            update_status("Dispositivo conectado en " + arduino_port, "success")
            update_connection_status(True)
        except Exception as e:
            speak("No se pudo establecer conexión. Por favor, revise el dispositivo.")
            log_message("No se pudo establecer conexión serial: " + str(e))
            update_status("Error de conexión: Verifique dispositivo", "error")
            update_connection_status(False)
            ser = None
    else:
        # No port with "Arduino" found
        speak("No se encontraron dispositivos Arduino conectados.")
        log_message("No se encontraron puertos con Arduino. Verifique que el Arduino esté conectado.")
        update_status("No se encontraron dispositivos Arduino", "error")



def update_status(message, status_type="info"):
    status_colors = {
        "info": {"fg": theme["status"]["info"], "bg": theme["status"]["info_bg"]},
        "success": {"fg": theme["status"]["success"], "bg": theme["status"]["success_bg"]},
        "warning": {"fg": theme["status"]["warning"], "bg": theme["status"]["warning_bg"]},
        "error": {"fg": theme["status"]["error"], "bg": theme["status"]["error_bg"]}
    }
    
    # Update the status label
    status_label.config(
        text=message,
        fg=status_colors[status_type]["fg"],
        bg=status_colors[status_type]["bg"]
    )
    
    # Make status bar visible with animation
    status_frame.config(bg=status_colors[status_type]["bg"])
    status_frame.tkraise()
    
    # Schedule status to fade after 5 seconds
    root.after(5000, lambda: status_frame.config(bg=theme["bg_medium"]))
    root.after(5000, lambda: status_label.config(
        text="Listo",
        fg=theme["text_muted"],
        bg=theme["bg_medium"]
    ))

def update_connection_status(connected):
    if connected:
        connection_indicator.config(bg=theme["success"])
        connection_text.config(text="Conectado")
    else:
        connection_indicator.config(bg=theme["error"])
        connection_text.config(text="Desconectado")

def update_training_status(active, mode=None):
    if active:
        training_indicator.config(bg=theme["accent"])
        training_text.config(text=f"Entrenamiento activo: {mode.capitalize()}")
    else:
        training_indicator.config(bg=theme["text_muted"])
        training_text.config(text="Entrenamiento inactivo")

def log_message(msg):
    log_text.configure(state=tk.NORMAL)
    
    # Get current time for timestamp
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    # Format the log entry with timestamp
    log_entry = f"[{timestamp}] {msg}\n"
    
    # Apply appropriate tag based on message content
    if "correcta" in msg.lower():
        log_text.insert(tk.END, log_entry, "success")
    elif "incorrecta" in msg.lower() or "error" in msg.lower():
        log_text.insert(tk.END, log_entry, "error")
    elif "seleccionada" in msg.lower():
        log_text.insert(tk.END, log_entry, "highlight")
    elif "escuchándote" in msg.lower():
        log_text.insert(tk.END, log_entry, "listening")
    else:
        log_text.insert(tk.END, log_entry, "normal")
        
    log_text.see(tk.END)
    log_text.configure(state=tk.DISABLED)

def load_words():
    global words_list
    try:
        with open(WORDS_FILENAME, "r", encoding="utf-8") as f:
            words_list = f.readlines()
        log_message(f"Archivo cargado: {WORDS_FILENAME} ({len(words_list)} palabras)")
        update_status(f"Diccionario cargado: {len(words_list)} palabras", "info")
    except Exception as e:
        error_msg = f"No se pudo cargar el archivo {WORDS_FILENAME}: {e}"
        messagebox.showerror("Error", error_msg)
        log_message(error_msg)
        update_status("Error al cargar diccionario", "error")

# Key bindings
def on_f_press(event):
    cancel_current_speech()
    init_serial()

def on_j_press(event):
    cancel_current_speech()
    global training_running
    if not training_running:
        # Visual feedback for key press
        btn_start.config(relief=tk.SUNKEN)
        root.after(100, lambda: btn_start.config(relief=tk.RAISED))
        
        threading.Thread(target=start_training, daemon=True).start()
    else:
        log_message("El entrenamiento ya se encuentra en ejecución. Presione D para cambiar el modo.")
        update_status("Entrenamiento en ejecución. Presione D para cambiar modo", "warning")

def on_d_press(event):
    cancel_current_speech()
    if training_running:
        # Visual feedback for key press
        btn_change.config(relief=tk.SUNKEN)
        root.after(100, lambda: btn_change.config(relief=tk.RAISED))
        
        threading.Thread(target=start_training, daemon=True).start()
    else:
        speak("El entrenamiento no ha iniciado. Presione J para iniciar el entrenamiento.")
        log_message("El entrenamiento no ha iniciado. Presione J para iniciar el entrenamiento.")
        update_status("Inicie el entrenamiento con J primero", "info")

def on_k_press(event):
    cancel_current_speech()
    global training_running
    training_running = False
    cancel_exercise_event.set()
    log_message("Cerrando la aplicación...")
    root.destroy()

def create_tooltip(widget, text):
    """Create a tooltip for a given widget."""
    def enter(event):
        # Create a toplevel window
        global tooltip
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)  # Remove window decorations
        
        # Position tooltip near widget
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        
        # Create a frame for the tooltip with a nice background
        tip_frame = tk.Frame(tooltip, bg=theme["tooltip_bg"], bd=1, relief=tk.SOLID)
        tip_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a label for the tooltip text
        tip_label = tk.Label(
            tip_frame, 
            text=text, 
            justify=tk.LEFT,
            bg=theme["tooltip_bg"],
            fg=theme["tooltip_text"],
            padx=8,
            pady=4,
            wraplength=250,
            font=(theme["font_family"], theme["font_size_small"])
        )
        tip_label.pack()
        
        # Position the tooltip
        tooltip.wm_geometry(f"+{x}+{y}")
    
    def leave(event):
        # Close the tooltip
        global tooltip
        if 'tooltip' in globals():
            tooltip.destroy()
            del globals()['tooltip']
    
    # Bind events to the widget
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)

# ----------------------- Enhanced UI Styling -----------------------

# Define a professional theme with modern colors
theme = {
    # Main colors
    "bg_dark": "#0A1929",            # Deep blue-black background
    "bg_medium": "#132F4C",          # Medium navy blue
    "bg_light": "#173A5E",           # Lighter navy blue
    "accent": "#3399FF",             # Bright blue accent
    "accent_hover": "#0A7AFF",       # Darker accent for hover
    
    # Text colors
    "text_bright": "#FFFFFF",        # Bright white text
    "text_normal": "#E6F0FF",        # Slightly off-white
    "text_muted": "#B2BAC2",         # Muted gray text
    
    # Status colors
    "success": "#4CAF50",            # Success green
    "success_bg": "#0A280A",         # Dark green background
    "warning": "#FFC107",            # Warning yellow
    "warning_bg": "#332D03",         # Dark yellow background
    "error": "#F44336",              # Error red 
    "error_bg": "#2C0B09",           # Dark red background
    "info": "#64B5F6",               # Info blue
    "info_bg": "#0A192F",            # Dark blue background
    
    # UI element colors
    "btn_primary": "#0078D7",        # Primary button blue
    "btn_secondary": "#2D4865",      # Secondary button gray-blue
    "btn_danger": "#D32F2F",         # Danger button red
    
    # Log colors
    "log_bg": "#0C1929",             # Log background (even darker)
    "log_border": "#264B73",         # Log border
    "log_text": "#E1F5FE",           # Log text color (light blue)
    
    # Tooltip
    "tooltip_bg": "#424242",         # Tooltip background
    "tooltip_text": "#FFFFFF",       # Tooltip text
    
    # Fonts
    "font_family": "Segoe UI",       # Modern sans-serif font
    "font_size_large": 16,           # Large font size (titles)
    "font_size_medium": 11,          # Medium font size (normal text)
    "font_size_small": 9,            # Small font size (status)
    
    # Status
    "status": {
        "info": "#64B5F6",           # Info blue
        "info_bg": "#0A192F",        # Dark blue background
        "success": "#4CAF50",        # Success green
        "success_bg": "#0A280A",     # Dark green background
        "warning": "#FFC107",        # Warning yellow
        "warning_bg": "#332D03",     # Dark yellow background
        "error": "#F44336",          # Error red
        "error_bg": "#2C0B09",       # Dark red background
    }
}

# Modern elevated button with hover effects
class ModernButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        self.hover_bg = kwargs.pop('hover_bg', theme["bg_light"])
        self.original_bg = kwargs.get('bg', theme["bg_medium"])
        self.original_fg = kwargs.get('fg', theme["text_bright"])
        self.corner_radius = kwargs.pop('corner_radius', 8)
        
        # Apply styling
        kwargs['relief'] = 'flat'
        kwargs['borderwidth'] = 0
        kwargs['padx'] = kwargs.get('padx', 18)
        kwargs['pady'] = kwargs.get('pady', 10)
        kwargs['font'] = kwargs.get('font', (theme["font_family"], theme["font_size_medium"], "bold"))
        
        super().__init__(master, **kwargs)
        
        # Bind hover events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        # Add shadow effect
        self.config(highlightbackground=self.original_bg, highlightthickness=1)
    
    def _on_enter(self, e):
        self['bg'] = self.hover_bg
    
    def _on_leave(self, e):
        self['bg'] = self.original_bg

# Apply custom styling to the UI
root = tk.Tk()
root.title("DotSense - Sistema Profesional de Entrenamiento Braille")

# Create a blue circle icon programmatically
def create_blue_circle_icon():
    try:
        # Create a 64x64 transparent image
        icon_size = 64
        icon = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        
        # Draw a black circle for a classic, professional look
        circle_color = "#000000"  # Pure black
        padding = 4
        draw.ellipse(
            [padding, padding, icon_size-padding, icon_size-padding], 
            fill=circle_color
        )
        
        # Save the icon to a temporary file
        icon_path = "temp_icon.png"
        icon.save(icon_path)
        
        # Load the icon and set it as the window icon
        window_icon = tk.PhotoImage(file=icon_path)
        root.iconphoto(False, window_icon)
        
        # Keep a reference to prevent garbage collection
        root.window_icon = window_icon
        
        # Remove the temporary file
        try:
            os.remove(icon_path)
        except:
            pass
            
    except Exception as e:
        print(f"Error creating window icon: {e}")

# Apply icon after the theme is defined later in the code
# We'll call this function after defining the theme

# Configure the default font for all widgets
default_font = font.nametofont("TkDefaultFont")
default_font.configure(family=theme["font_family"], size=theme["font_size_medium"])
root.option_add("*Font", default_font)

# We're intentionally not setting the window icon in the title bar
# as per client request to keep it clean

# Configure window size and position
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = 800
window_height = 650
x_coordinate = int((screen_width - window_width) / 2)
y_coordinate = int((screen_height - window_height) / 2)
root.geometry(f"{window_width}x{window_height}+{x_coordinate}+{y_coordinate}")
root.configure(bg=theme["bg_dark"])

# Make window resizable but prevent maximizing
root.minsize(700, 550)
root.maxsize(900, 750)  # Set a reasonable maximum size

# Disable the maximize button (Windows-specific)
root.resizable(True, True)
try:
    # This works on Windows
    root.attributes('-toolwindow', False)  # Keep normal window style
    root.attributes('-fullscreen', False)  # Ensure not fullscreen
    
    # Prevent maximize using Windows API if available
    if root.tk.call('tk', 'windowingsystem') == 'win32':
        # Disable maximize button
        root.after(100, lambda: root.tk.call('wm', 'attributes', '.', '-toolwindow', '0'))
        # Alternative approach
        root.after(100, lambda: root.state('normal'))
except:
    pass  # Silently fail if these attributes are not supported

# Create a custom frame system for a more professional look
main_container = tk.Frame(root, bg=theme["bg_dark"])
main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

# Create a header with logo and title
header_frame = tk.Frame(main_container, bg=theme["bg_dark"], height=80)
header_frame.pack(fill=tk.X, pady=(0, 20))

# Create a modern title with shadow effect
title_frame = tk.Frame(header_frame, bg=theme["bg_dark"])
title_frame.pack(side=tk.LEFT, fill=tk.Y)

# Try to load logo image
try:
    logo_img = tk.PhotoImage(file="dotsense.png").subsample(4, 4)  # Scale down the image
    logo_label = tk.Label(title_frame, image=logo_img, bg=theme["bg_dark"])
    logo_label.pack(side=tk.LEFT, padx=(0, 15))
except Exception as e:
    print(f"Error loading logo: {e}")
    # Create a placeholder logo with a stylized "D"
    logo_frame = tk.Frame(title_frame, width=60, height=60, bg=theme["accent"])
    logo_frame.pack(side=tk.LEFT, padx=(0, 15))
    logo_text = tk.Label(logo_frame, text="D", font=(theme["font_family"], 32, "bold"), 
                        fg=theme["text_bright"], bg=theme["accent"])
    logo_text.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

# Title text
title_label = tk.Label(title_frame, text="DotSense", font=(theme["font_family"], 28, "bold"), 
                     bg=theme["bg_dark"], fg=theme["accent"])
title_label.pack(side=tk.TOP, anchor=tk.W)

subtitle_label = tk.Label(title_frame, text="Sistema Profesional de Entrenamiento Braille", 
                        font=(theme["font_family"], 12), 
                        bg=theme["bg_dark"], fg=theme["text_muted"])
subtitle_label.pack(side=tk.TOP, anchor=tk.W)

# Status indicators in header
status_indicators = tk.Frame(header_frame, bg=theme["bg_dark"])
status_indicators.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

# Arduino connection status
connection_frame = tk.Frame(status_indicators, bg=theme["bg_dark"], padx=5, pady=3)
connection_frame.pack(side=tk.TOP, anchor=tk.E, pady=2)

connection_indicator = tk.Frame(connection_frame, width=12, height=12, bg=theme["error"], 
                             borderwidth=0, relief=tk.RAISED)
connection_indicator.pack(side=tk.LEFT, padx=(0, 5))
connection_text = tk.Label(connection_frame, text="Desconectado", font=(theme["font_family"], theme["font_size_small"]), 
                         bg=theme["bg_dark"], fg=theme["text_muted"])
connection_text.pack(side=tk.LEFT)

# Training status
training_frame = tk.Frame(status_indicators, bg=theme["bg_dark"], padx=5, pady=3)
training_frame.pack(side=tk.TOP, anchor=tk.E, pady=2)

training_indicator = tk.Frame(training_frame, width=12, height=12, bg=theme["text_muted"], 
                           borderwidth=0, relief=tk.RAISED)
training_indicator.pack(side=tk.LEFT, padx=(0, 5))
training_text = tk.Label(training_frame, text="Entrenamiento inactivo", font=(theme["font_family"], theme["font_size_small"]), 
                       bg=theme["bg_dark"], fg=theme["text_muted"])
training_text.pack(side=tk.LEFT)

# Divider between header and content
divider = tk.Frame(main_container, height=1, bg=theme["bg_light"])
divider.pack(fill=tk.X, pady=(0, 15))

# Create a container for the controls and content
content_container = tk.Frame(main_container, bg=theme["bg_dark"])
content_container.pack(fill=tk.BOTH, expand=True)

# Create a sidebar for controls
sidebar = tk.Frame(content_container, bg=theme["bg_medium"], width=220)
sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
sidebar.pack_propagate(False)  # Prevent the frame from shrinking

# Sidebar title
sidebar_title = tk.Label(sidebar, text="Controles", font=(theme["font_family"], theme["font_size_medium"], "bold"), 
                       bg=theme["bg_medium"], fg=theme["text_bright"])
sidebar_title.pack(pady=(15, 10), padx=10, anchor=tk.W)

# Keyboard shortcuts frame
shortcuts_frame = tk.LabelFrame(sidebar, text="Atajos de Teclado", bg=theme["bg_medium"], fg=theme["text_bright"],
                             font=(theme["font_family"], theme["font_size_small"], "bold"),
                             padx=10, pady=10)
shortcuts_frame.pack(fill=tk.X, padx=10, pady=5)

# Add keyboard shortcuts with modern styling
def create_shortcut_item(parent, key, action):
    frame = tk.Frame(parent, bg=theme["bg_medium"])
    frame.pack(fill=tk.X, pady=3)
    
    key_label = tk.Label(frame, text=key, width=3, font=(theme["font_family"], theme["font_size_medium"], "bold"),
                       bg=theme["bg_light"], fg=theme["accent"], padx=8, pady=2)
    key_label.pack(side=tk.LEFT)
    
    action_label = tk.Label(frame, text=action, font=(theme["font_family"], theme["font_size_small"]),
                          bg=theme["bg_medium"], fg=theme["text_normal"], anchor=tk.W)
    action_label.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

create_shortcut_item(shortcuts_frame, "F", "Conectar Arduino")
create_shortcut_item(shortcuts_frame, "J", "Iniciar Entrenamiento")
create_shortcut_item(shortcuts_frame, "D", "Cambiar Modo")
create_shortcut_item(shortcuts_frame, "K", "Salir")

# Action buttons in sidebar
buttons_frame = tk.Frame(sidebar, bg=theme["bg_medium"], padx=10, pady=10)
buttons_frame.pack(fill=tk.X, padx=10, pady=10)

btn_serial = ModernButton(
    buttons_frame, 
    text="Conectar Arduino", 
    command=init_serial, 
    bg=theme["btn_primary"], 
    fg=theme["text_bright"],
    hover_bg="#005FB3",  # Slightly darker blue
    corner_radius=6,
    padx=10, 
    pady=8,
)
btn_serial.pack(fill=tk.X, pady=(0, 10))
create_tooltip(btn_serial, "Establece conexión con el dispositivo Arduino")

btn_start = ModernButton(
    buttons_frame, 
    text="Iniciar Entrenamiento", 
    command=lambda: threading.Thread(target=start_training, daemon=True).start(),
    bg=theme["accent"], 
    fg=theme["text_bright"],
    hover_bg=theme["accent_hover"],
    corner_radius=6,
    padx=10, 
    pady=8,
)
btn_start.pack(fill=tk.X, pady=(0, 10))
create_tooltip(btn_start, "Inicia el modo de entrenamiento (palabras o letras)")

btn_change = ModernButton(
    buttons_frame, 
    text="Cambiar Modo", 
    command=lambda: threading.Thread(target=start_training, daemon=True).start() if training_running else None,
    bg=theme["btn_secondary"], 
    fg=theme["text_bright"],
    hover_bg="#3A5A7D",  # Slightly darker blue-gray
    corner_radius=6,
    padx=10, 
    pady=8,
)
btn_change.pack(fill=tk.X, pady=(0, 10))
create_tooltip(btn_change, "Cambia entre el modo de palabras y letras")

btn_exit = ModernButton(
    buttons_frame, 
    text="Salir", 
    command=lambda: on_k_press(None),
    bg=theme["btn_danger"], 
    fg=theme["text_bright"],
    hover_bg="#B71C1C",  # Slightly darker red
    corner_radius=6,
    padx=10, 
    pady=8,
)
btn_exit.pack(fill=tk.X, pady=(20, 0))
create_tooltip(btn_exit, "Cierra la aplicación")

# App version at bottom of sidebar
version_label = tk.Label(sidebar, text="Versión 1.0", font=(theme["font_family"], theme["font_size_small"]),
                       bg=theme["bg_medium"], fg=theme["text_muted"])
version_label.pack(side=tk.BOTTOM, pady=10)

# Main content area (log)
main_content = tk.Frame(content_container, bg=theme["bg_dark"])
main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Enhanced log frame with title and borders
log_frame = tk.Frame(main_content, bg=theme["bg_medium"], bd=1, highlightbackground=theme["log_border"], 
                   highlightthickness=1)
log_frame.pack(fill=tk.BOTH, expand=True)

# Log header with title and subtle gradient
log_header = tk.Frame(log_frame, bg=theme["bg_medium"], height=36)
log_header.pack(fill=tk.X)

# Canvas for gradient header that will resize with the window
header_canvas = tk.Canvas(log_header, bg=theme["bg_medium"], height=36, bd=0, highlightthickness=0)
header_canvas.pack(fill=tk.X)

# Function to redraw the gradient header when the window resizes
def redraw_header_gradient(event=None):
    # Get current canvas width
    current_width = header_canvas.winfo_width()
    
    # Clear previous gradient
    header_canvas.delete("gradient")
    
    # Create gradient for header background
    for i in range(36):
        # Gradient from medium to slightly darker
        r1, g1, b1 = int('13', 16), int('2F', 16), int('4C', 16)  # bg_medium
        r2, g2, b2 = int('0C', 16), int('19', 16), int('29', 16)  # log_bg
        r = int(r1 + (r2 - r1) * (i / 36))
        g = int(g1 + (g2 - g1) * (i / 36))
        b = int(b1 + (b2 - b1) * (i / 36))
        color = f'#{r:02x}{g:02x}{b:02x}'
        header_canvas.create_line(0, i, current_width, i, fill=color, tags=("gradient",))
    
    # Redraw the title text
    header_canvas.delete("title")
    header_canvas.create_text(20, 18, text="Registro de Actividad", 
                           font=(theme["font_family"], theme["font_size_medium"], "bold"), 
                           fill=theme["text_bright"], anchor=tk.W, tags=("title",))

# Bind the resize event to redraw the gradient
header_canvas.bind("<Configure>", redraw_header_gradient)

# Initial draw of the gradient (will be called after the window appears)
root.update_idletasks()
root.after(100, redraw_header_gradient)

# Create a container for the log and scrollbar
log_container = tk.Frame(log_frame, bg=theme["log_bg"])
log_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

# Custom scrollbar with modern styling
class ModernScrollbar(tk.Canvas):
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop('bg', theme["bg_medium"])
        width = kwargs.pop('width', 12)
        self.command = kwargs.pop('command', None)
        
        super().__init__(parent, bg=bg, width=width, highlightthickness=0, **kwargs)
        
        # Scrollbar colors
        self.thumb_color = theme["accent"]
        self.thumb_hover_color = theme["accent_hover"]
        self.trough_color = theme["bg_medium"]
        
        # Thumb dimensions and position
        self.thumb_width = width - 4
        self.thumb_height = 30
        self.thumb_x = 2
        self.thumb_y = 0
        
        # Draw the initial thumb
        self.thumb = self.create_rectangle(
            self.thumb_x, self.thumb_y, 
            self.thumb_x + self.thumb_width, self.thumb_y + self.thumb_height,
            fill=self.thumb_color, outline="", width=0, tags=("thumb",)
        )
        
        # Bind events
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_motion)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        
        # Variables for dragging
        self.pressed = False
        self.start_y = 0
        
    def set(self, first, last):
        # Update thumb position based on scrollbar values
        height = self.winfo_height()
        thumb_position = float(first) * height
        thumb_height = max(10, (float(last) - float(first)) * height)
        
        # Update thumb dimensions
        self.thumb_height = thumb_height
        self.thumb_y = thumb_position
        
        # Redraw thumb
        self.coords(
            self.thumb,
            self.thumb_x, self.thumb_y,
            self.thumb_x + self.thumb_width, self.thumb_y + self.thumb_height
        )
        
    def on_press(self, event):
        self.pressed = True
        self.start_y = event.y
        
    def on_motion(self, event):
        if self.pressed:
            delta_y = event.y - self.start_y
            self.start_y = event.y
            
            # Calculate new position
            height = self.winfo_height()
            move_frac = delta_y / height
            
            if self.command:
                self.command("moveto", str(float(self.thumb_y / height) + move_frac))
                
    def on_release(self, event):
        self.pressed = False
        
    def on_enter(self, event):
        self.itemconfig(self.thumb, fill=self.thumb_hover_color)
        
    def on_leave(self, event):
        self.itemconfig(self.thumb, fill=self.thumb_color)

# Create the scrollbar and text widget
scrollbar = ModernScrollbar(log_container, command=None, width=12)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Enhanced text box with custom colors and font
log_text = tk.Text(
    log_container, 
    wrap=tk.WORD, 
    height=15, 
    state=tk.DISABLED, 
    font=(theme["font_family"], theme["font_size_medium"]), 
    bg=theme["log_bg"], 
    fg=theme["log_text"],
    padx=15,
    pady=15,
    borderwidth=0,
    insertbackground=theme["text_bright"],
    selectbackground=theme["accent"],
    selectforeground=theme["text_bright"]
)
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
log_text.config(yscrollcommand=scrollbar.set)
scrollbar.command = log_text.yview

# Configure text tags for different log message types
log_text.tag_configure("normal", foreground=theme["log_text"])
log_text.tag_configure("success", foreground=theme["success"])
log_text.tag_configure("error", foreground=theme["error"])
log_text.tag_configure("warning", foreground=theme["warning"])
log_text.tag_configure("highlight", foreground=theme["accent"])
log_text.tag_configure("listening", foreground="#64B5F6")  # Light blue for listening

# Status bar at the bottom
status_frame = tk.Frame(main_container, bg=theme["bg_medium"], height=30)
status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(15, 0))
status_label = tk.Label(status_frame, text="Listo", font=(theme["font_family"], theme["font_size_small"]), 
                      bg=theme["bg_medium"], fg=theme["text_muted"], padx=10, pady=5)
status_label.pack(side=tk.LEFT, fill=tk.X)

# Bind keys: F for serial, J to start training, D to change mode, K to close.
root.bind("<f>", on_f_press)
root.bind("<F>", on_f_press)
root.bind("<j>", on_j_press)
root.bind("<J>", on_j_press)
root.bind("<d>", on_d_press)
root.bind("<D>", on_d_press)
root.bind("<k>", on_k_press)
root.bind("<K>", on_k_press)

# Create a custom messagebox style
def custom_messagebox(title, message, icon=messagebox.INFO):
    # Override the standard messagebox with a custom styled one
    result = messagebox._show(title, message, icon, messagebox.OK)
    
    # Find all toplevels created (our messagebox)
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel) and w.wm_title() == title:
            # Style the messagebox
            w.configure(bg=theme["bg_medium"])
            
            # Style all children widgets (labels, buttons, etc.)
            for child in w.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=theme["bg_medium"], fg=theme["text_bright"])
                elif isinstance(child, tk.Button):
                    child.configure(
                        bg=theme["accent"],
                        fg=theme["text_bright"],
                        activebackground=theme["accent_hover"],
                        activeforeground=theme["text_bright"],
                        relief="flat",
                        borderwidth=0,
                        font=(theme["font_family"], theme["font_size_medium"]),
                        padx=15,
                        pady=5
                    )
    
    return result

# Override messagebox functions with our styled versions
original_showinfo = messagebox.showinfo
original_showwarning = messagebox.showwarning
original_showerror = messagebox.showerror

messagebox.showinfo = lambda title, message: custom_messagebox(title, message, messagebox.INFO)
messagebox.showwarning = lambda title, message: custom_messagebox(title, message, messagebox.WARNING)
messagebox.showerror = lambda title, message: custom_messagebox(title, message, messagebox.ERROR)

# Load words
load_words()

# Initialize with inactive training
update_training_status(False)

# Disable window maximization more thoroughly for different platforms
def disable_maximize():
    try:
        # For Windows
        if root.tk.call('tk', 'windowingsystem') == 'win32':
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(ctypes.windll.user32.GetForegroundWindow())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            style = style & ~0x10000  # Remove WS_MAXIMIZEBOX
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, style)
    except:
        pass

    # For other platforms or as a fallback
    try:
        # Bind Alt+F9 and Alt+F10 (common maximize shortcuts) to do nothing
        root.bind('<Alt-F9>', lambda e: 'break')
        root.bind('<Alt-F10>', lambda e: 'break')
        
        # Handle double-click on title bar (common maximize action)
        def prevent_maximize(event):
            return 'break'
        
        # Try to intercept maximize attempts
        root.bind('<Map>', lambda e: root.state('normal') if root.state() == 'zoomed' else None)
    except:
        pass

# Call after a short delay to ensure window is fully created
root.after(100, disable_maximize)

# Schedule welcome speech. It can be canceled by any key press.
root.after(1000, lambda: speak("Bienvenido a DotSense. Inicie la conexión con el dispositivo en un puerto USB con F, presione J para iniciar el entrenamiento, D para cambiar el modo, y K para cerrar la aplicación."))

# Call the create icon function now that theme is defined
create_blue_circle_icon()

# Start the application
root.mainloop()
