import os
import sys
import json
import threading
import queue
import asyncio
import collections
import urllib.request
import tarfile
from tkinter import filedialog
import io
import base64
import zlib
import winsound
import glob

import customtkinter as ctk
import websockets
import sounddevice as sd
import keyboard
from PIL import Image, ImageDraw, ImageTk
import pystray

from bnbphoneticparser import BengaliToBanglish
from assets import LOGO_D_DATA, LOGO_L_DATA

# --- CONSTANTS & SETTINGS ---
APP_DIR_NAME = "BakkorupVoiceTyping"
if os.name == 'nt':
    app_data_dir = os.path.join(os.getenv('APPDATA'), APP_DIR_NAME)
else:
    app_data_dir = os.path.join(os.path.expanduser("~"), f".{APP_DIR_NAME}")

os.makedirs(app_data_dir, exist_ok=True)
MODELS_DIR = os.path.join(app_data_dir, "Models")
os.makedirs(MODELS_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(app_data_dir, "settings.json")
HOTKEY_TOGGLE = "alt+v"
HOTKEY_BANGLA = "alt+1"
HOTKEY_BANGLISH = "alt+2"
SAMPLE_RATE = 16000
PRE_BUFFER_MS = 300
MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bn-vosk-2026-02-09.tar.bz2"
MODEL_FOLDER_NAME = "sherpa-onnx-streaming-zipformer-bn-vosk-2026-02-09"

DEFAULT_SETTINGS = {
    "connection_mode": "Local",
    "remote_url": "ws://127.0.0.1:11000/stream",
    "auth_token": "my_secret_token_123",
    "typing_mode": "Bangla",
    "model_path": MODELS_DIR,
    "theme": "Dark"
}

# --- GLOBAL STATE ---
settings = DEFAULT_SETTINGS.copy()
is_listening = False
audio_queue = queue.Queue()
pre_buffer = collections.deque(maxlen=int(SAMPLE_RATE * (PRE_BUFFER_MS / 1000.0) / (SAMPLE_RATE * 0.1))) 
b2b = BengaliToBanglish()
async_loop = None
tray_icon = None

# --- DECODE ASSETS ---
raw_logo_d_data = base64.b64decode(LOGO_D_DATA)
base_logo_d_img = Image.open(io.BytesIO(raw_logo_d_data)).convert("RGBA")

raw_logo_l_data = base64.b64decode(LOGO_L_DATA)
base_logo_l_img = Image.open(io.BytesIO(raw_logo_l_data)).convert("RGBA")

# --- TRANSLITERATION ---
bn_to_en = {
    'অ': 'o', 'আ': 'a', 'ই': 'i', 'ঈ': 'i', 'উ': 'u', 'ঊ': 'u', 'ঋ': 'ri', 'এ': 'e', 'ঐ': 'oi', 'ও': 'o', 'ঔ': 'ou',
    'ক': 'k', 'খ': 'kh', 'গ': 'g', 'ঘ': 'gh', 'ঙ': 'ng', 'চ': 'ch', 'ছ': 'chh', 'জ': 'j', 'ঝ': 'jh', 'ঞ': 'n',
    'ট': 't', 'ঠ': 'th', 'ড': 'd', 'ঢ': 'dh', 'ণ': 'n', 'ত': 't', 'থ': 'th', 'দ': 'd', 'ধ': 'dh', 'ন': 'n',
    'প': 'p', 'ফ': 'f', 'ব': 'b', 'ভ': 'v', 'ম': 'm', 'য': 'j', 'র': 'r', 'ল': 'l', 'শ': 'sh', 'ষ': 'sh', 'স': 's', 'হ': 'h',
    'ড়': 'r', 'ঢ়': 'rh', 'য়': 'y', 'ৎ': 't', 'ং': 'ng', 'ঃ': 'h', 'ঁ': 'n',
    'া': 'a', 'ি': 'i', 'ী': 'i', 'ু': 'u', 'ূ': 'u', 'ৃ': 'ri', 'ে': 'e', 'ৈ': 'oi', 'ো': 'o', 'ৌ': 'ou',
    '্': '', '্য': 'y', '্র': 'r'
}

def custom_transliterate(word):
    return "".join(bn_to_en.get(char, char) for char in word)

def safe_parse(text):
    words = text.split()
    res = []
    for w in words:
        if all(c.isascii() for c in w):
            res.append(w)
            continue
        try:
            res.append(b2b.parse(w).lower())
        except Exception:
            res.append(custom_transliterate(w))
    return " ".join(res)

def type_text(text):
    if not text.strip(): return
    final_text = text if settings["typing_mode"] == "Bangla" else safe_parse(text)
    print(f"Typing: {final_text}")
    keyboard.write(final_text + " ")

# --- AUDIO & NETWORK ENGINE ---
def audio_callback(indata, frames, time, status):
    frame_copy = indata.copy()
    pre_buffer.append(frame_copy)
    if is_listening:
        audio_queue.put(frame_copy)

async def network_streamer():
    global b2b, is_listening, recognizer
    
    while True:
        if settings["connection_mode"] == "Local":
            if recognizer is None:
                full_model_dir = os.path.join(settings["model_path"], MODEL_FOLDER_NAME)
                try:
                    import sherpa_onnx
                    encoder_list = glob.glob(f"{full_model_dir}/encoder*.onnx")
                    if not encoder_list:
                        app.update_status("Offline Model Missing!", ("#D70015", "#FF453A"))
                        await asyncio.sleep(2)
                        continue
                        
                    app.update_status("Loading Local Engine...", ("#B25000", "#FF9F0A"))
                    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                        encoder=encoder_list[0], 
                        decoder=glob.glob(f"{full_model_dir}/decoder*.onnx")[0], 
                        joiner=glob.glob(f"{full_model_dir}/joiner*.onnx")[0], 
                        tokens=f"{full_model_dir}/tokens.txt",
                        num_threads=1, sample_rate=SAMPLE_RATE, feature_dim=80, enable_endpoint_detection=True,
                        rule1_min_trailing_silence=1.2, rule2_min_trailing_silence=0.8, rule3_min_utterance_length=300,
                    )
                    app.update_status("Ready (Offline Mode)", ("#007A33", "#32D74B"))
                except Exception as e:
                    app.update_status("Local Engine Error", ("#D70015", "#FF453A"))
                    print(e)
                    await asyncio.sleep(2)
                    continue
                    
            stream = recognizer.create_stream()
            last_text = ""
            last_state = False
            
            while settings["connection_mode"] == "Local":
                if is_listening:
                    if not last_state: last_state = True
                    try:
                        data = audio_queue.get(timeout=0.01)
                        import numpy as np
                        audio_data = np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32) / 32768.0
                        stream.accept_waveform(SAMPLE_RATE, audio_data)
                        while recognizer.is_ready(stream): recognizer.decode_stream(stream)
                        if recognizer.is_endpoint(stream):
                            text = recognizer.get_result(stream)
                            if text: type_text(text)
                            recognizer.reset(stream)
                            last_text = ""
                    except queue.Empty:
                        pass
                else:
                    if last_state:
                        last_state = False
                        stream.accept_waveform(SAMPLE_RATE, [0.0]*int(SAMPLE_RATE*0.1))
                        while recognizer.is_ready(stream): recognizer.decode_stream(stream)
                        text = recognizer.get_result(stream)
                        if text: type_text(text)
                        recognizer.reset(stream)
                        last_text = ""
                    await asyncio.sleep(0.05)
            
        else:
            url = f"{settings['remote_url']}?token={settings['auth_token']}"
            try:
                headers = {}
                if settings['auth_token']:
                    headers["Authorization"] = f"Bearer {settings['auth_token']}"
                    
                async with websockets.connect(url, ping_interval=None, ping_timeout=None, additional_headers=headers) as ws:
                    print("Connected to remote server.")
                    app.update_status("Connected to Remote Server", ("#007A33", "#32D74B"))
                    frame_size = int(SAMPLE_RATE * 0.1)
                    bytes_per_frame = frame_size * 2
                    audio_buffer = b""
                    last_state = False
                    
                    while settings["connection_mode"] == "Remote":
                        if is_listening:
                            if not last_state: last_state = True
                            try:
                                data = audio_queue.get(timeout=0.01)
                                audio_buffer += bytes(data)
                                while len(audio_buffer) >= bytes_per_frame:
                                    chunk = audio_buffer[:bytes_per_frame]
                                    audio_buffer = audio_buffer[bytes_per_frame:]
                                    await ws.send(chunk)
                            except queue.Empty:
                                pass
                        else:
                            if last_state:
                                last_state = False
                                if len(audio_buffer) > 0:
                                    await ws.send(audio_buffer)
                                    audio_buffer = b""
                                    await ws.send(json.dumps({"action": "stop"}))
                            await asyncio.sleep(0.05)
                        
                        try:
                            response = await asyncio.wait_for(ws.recv(), timeout=0.01)
                            res_json = json.loads(response)
                            if res_json.get("type") == "final":
                                type_text(res_json.get("text", ""))
                        except asyncio.TimeoutError:
                            pass
                        except websockets.exceptions.ConnectionClosedError:
                            break
                            
            except Exception as e:
                app.update_status("Remote Disconnected - Retrying...", ("#D70015", "#FF453A"))
                await asyncio.sleep(2)

def start_asyncio_loop():
    global async_loop
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    
    frame_size = int(SAMPLE_RATE * 0.1)
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', 
                            blocksize=frame_size, callback=audio_callback)
    stream.start()
    
    async_loop.run_until_complete(network_streamer())

# --- HOTKEYS & SYSTRAY ---
def play_sound_cue(start):
    def sound_thread():
        if start:
            winsound.Beep(700, 100)
            winsound.Beep(1000, 150)
        else:
            winsound.Beep(1000, 100)
            winsound.Beep(700, 150)
    threading.Thread(target=sound_thread, daemon=True).start()

def update_tray_icon():
    global tray_icon
    if tray_icon:
        icon_img = base_logo_d_img.copy()
        draw = ImageDraw.Draw(icon_img)
        w, h = icon_img.size
        # Tray dot
        dot_r = int(min(w, h) * 0.25)
        color = "#32D74B" if is_listening else "#FF453A"
        
        margin = int(min(w, h) * 0.05)
        bbox = (w - dot_r*2 - margin, h - dot_r*2 - margin, w - margin, h - margin)
        draw.ellipse((bbox[0]-3, bbox[1]-3, bbox[2]+3, bbox[3]+3), fill="#1E1E1E")
        draw.ellipse(bbox, fill=color)
        
        tray_icon.icon = icon_img

def toggle_listening():
    global is_listening
    is_listening = not is_listening
    if is_listening:
        play_sound_cue(True)
        app.toggle_btn.configure(text="STOP LISTENING", fg_color="#EF4444", hover_color="#DC2626", border_width=0, text_color="white")
        while not audio_queue.empty(): audio_queue.get()
        for chunk in list(pre_buffer):
            audio_queue.put(chunk)
    else:
        play_sound_cue(False)
        app.toggle_btn.configure(text="START LISTENING", fg_color="#10A37F", hover_color="#0E906F", border_width=0, text_color="white")
    update_tray_icon()

def set_mode_hotkey(mode):
    settings["typing_mode"] = mode
    app.mode_var.set(mode)
    if hasattr(app, 'update_mode_ui'):
        app.update_mode_ui(mode)
    app.save_settings()
    winsound.Beep(1200, 50)
    if tray_icon:
        tray_icon.update_menu()

# --- GUI APP ---
class VoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Load Settings immediately so theme is available
        self.load_settings()
        
        # Clean Dark Theme setup
        self.configure(fg_color="#18181A")
        ctk.set_appearance_mode(settings.get("theme", "Dark"))
        
        self.title("Bakkorup")
        
        # Set App ID for Windows to show correct icon in taskbar
        try:
            import ctypes
            myappid = 'bakkorup.voice.typing.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if not os.path.exists(icon_path):
                base_logo_d_img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            self.iconbitmap(icon_path)
        except Exception:
            icon_photo = ImageTk.PhotoImage(base_logo_d_img)
            self.iconphoto(False, icon_photo)
        
        # --- Borderless & Transparent Background Setup ---
        self.withdraw()
        self.overrideredirect(True)
        self.geometry("420x730")
        
        self.configure(fg_color="#000001")
        self.wm_attributes("-transparentcolor", "#000001")
        
        def initial_show():
            self.deiconify()
            self.force_taskbar()
            
        self.after(200, initial_show)
        
        # Main Container
        self.main_frame = ctk.CTkFrame(self, corner_radius=25, fg_color=("#fff8eb", "#1E1E1E"))
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # --- Custom Draggable Title Bar ---
        self.title_bar = ctk.CTkFrame(self.main_frame, height=35, fg_color="transparent")
        self.title_bar.pack(fill="x", padx=10, pady=(20, 0))
        
        def start_move(event):
            self.x = event.x
            self.y = event.y

        def do_move(event):
            x = self.winfo_x() + event.x - self.x
            y = self.winfo_y() + event.y - self.y
            self.geometry(f"+{x}+{y}")

        self.title_bar.bind("<ButtonPress-1>", start_move)
        self.title_bar.bind("<B1-Motion>", do_move)
        
        self.close_btn = ctk.CTkButton(self.title_bar, text="✕", width=30, height=30, corner_radius=15, font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color="transparent", hover_color="#EF4444", text_color=("#18181B", "white"), command=self.hide_to_tray)
        self.close_btn.pack(side="right")
        
        self.min_btn = ctk.CTkButton(self.title_bar, text="—", width=30, height=30, corner_radius=15, font=ctk.CTkFont(size=14, weight="bold"),
                                     fg_color="transparent", hover_color=("#D4D4D8", "#52525B"), text_color=("#18181B", "white"), command=self.hide_to_tray)
        self.min_btn.pack(side="right", padx=5)

        self.current_theme = settings.get("theme", "Dark")
        initial_theme_icon = "◑" if self.current_theme == "Light" else "◐"
        
        def toggle_theme():
            if self.current_theme == "Dark":
                self.current_theme = "Light"
                ctk.set_appearance_mode("Light")
                self.theme_btn.configure(text="◑")
            else:
                self.current_theme = "Dark"
                ctk.set_appearance_mode("Dark")
                self.theme_btn.configure(text="◐")
            settings["theme"] = self.current_theme
            self.save_settings()
                
        self.theme_btn = ctk.CTkButton(self.title_bar, text=initial_theme_icon, width=30, height=30, corner_radius=15, font=ctk.CTkFont(size=18, weight="bold"),
                                       fg_color="transparent", hover_color=("#C3AA96", "#52525B"), text_color=("#18181B", "white"), command=toggle_theme)
        self.theme_btn.pack(side="right", padx=2)

        self.title_lbl = ctk.CTkLabel(self.title_bar, text="Bakkorup", font=ctk.CTkFont(size=13, weight="bold"), text_color=("#52525B", "#A1A1AA"))
        self.title_lbl.pack(side="left", padx=10)
        self.title_lbl.bind("<ButtonPress-1>", start_move)
        self.title_lbl.bind("<B1-Motion>", do_move)
        
        # Logo
        self.logo_img = ctk.CTkImage(light_image=base_logo_l_img, dark_image=base_logo_d_img, size=(160, 160))
        self.logo_label = ctk.CTkLabel(self.main_frame, text="", image=self.logo_img)
        self.logo_label.pack(pady=(10, 10))
        
        # Status Label
        self.status_lbl = ctk.CTkLabel(self.main_frame, text="Status: Waiting for input...", text_color=("#52525B", "#8E8E93"), font=ctk.CTkFont(size=14))
        self.status_lbl.pack(pady=5)
        
        # Mode Selection
        self.mode_var = ctk.StringVar(value=settings["typing_mode"])
        
        self.mode_frame = ctk.CTkFrame(self.main_frame, fg_color=("#E4E4E7", "#27272A"), corner_radius=12, height=40)
        self.mode_frame.pack(pady=(2, 5), padx=30, fill="x")
        self.mode_frame.pack_propagate(False)
        
        def set_mode(val):
            self.mode_var.set(val)
            self.save_settings()
            self.update_mode_ui(val)
            
        self.btn_bangla = ctk.CTkButton(self.mode_frame, text="Bangla", corner_radius=10, fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"), command=lambda: set_mode("Bangla"))
        self.btn_banglish = ctk.CTkButton(self.mode_frame, text="Banglish", corner_radius=10, fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"), command=lambda: set_mode("Banglish"))
        self.btn_bangla.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.btn_banglish.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        def update_mode_ui(val):
            if val == "Bangla":
                self.btn_bangla.configure(fg_color="#10A37F", hover_color="#0E906F", text_color="white")
                self.btn_banglish.configure(fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"))
            else:
                self.btn_banglish.configure(fg_color="#10A37F", hover_color="#0E906F", text_color="white")
                self.btn_bangla.configure(fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"))
        self.update_mode_ui = update_mode_ui
        self.update_mode_ui(settings["typing_mode"])

        # Connection Mode
        self.conn_var = ctk.StringVar(value=settings["connection_mode"])
        
        self.conn_frame = ctk.CTkFrame(self.main_frame, fg_color=("#E4E4E7", "#27272A"), corner_radius=12, height=40)
        self.conn_frame.pack(pady=(2, 5), padx=30, fill="x")
        self.conn_frame.pack_propagate(False)
        
        def set_conn(val):
            self.conn_var.set(val)
            self.on_conn_change(val)
            self.update_conn_ui(val)
            
        self.btn_local = ctk.CTkButton(self.conn_frame, text="Local", corner_radius=10, fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"), command=lambda: set_conn("Local"))
        self.btn_remote = ctk.CTkButton(self.conn_frame, text="Remote", corner_radius=10, fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"), command=lambda: set_conn("Remote"))
        self.btn_local.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.btn_remote.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        
        def update_conn_ui(val):
            if val == "Local":
                self.btn_local.configure(fg_color="#10A37F", hover_color="#0E906F", text_color="white")
                self.btn_remote.configure(fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"))
            else:
                self.btn_remote.configure(fg_color="#10A37F", hover_color="#0E906F", text_color="white")
                self.btn_local.configure(fg_color="transparent", hover_color=("#D4D4D8", "#3F3F46"), text_color=("#18181B", "white"))
        self.update_conn_ui = update_conn_ui
        self.update_conn_ui(settings["connection_mode"])
        
        # Configuration Area
        self.cfg_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.cfg_frame.pack(pady=5, fill="both", expand=True)
        
        # Remote Config
        self.remote_frame = ctk.CTkFrame(self.cfg_frame, fg_color="transparent")
        self.url_entry = ctk.CTkEntry(self.remote_frame, width=280, height=35, border_color=("#D4D4D8", "#3A3A3C"), fg_color=("#FFFFFF", "#18181A"), placeholder_text="Cloud Server URL", corner_radius=10, text_color=("#18181B", "white"))
        self.url_entry.insert(0, settings["remote_url"])
        self.url_entry.pack(pady=5)
        
        self.token_frame = ctk.CTkFrame(self.remote_frame, fg_color="transparent")
        self.token_frame.pack(pady=5)
        self.token_entry = ctk.CTkEntry(self.token_frame, width=235, height=35, show="*", border_color=("#D4D4D8", "#3A3A3C"), fg_color=("#FFFFFF", "#18181A"), placeholder_text="Auth Token", corner_radius=10, text_color=("#18181B", "white"))
        self.token_entry.insert(0, settings["auth_token"])
        self.token_entry.pack(side="left", padx=(0, 5))
        
        self.show_pass = False
        def toggle_pass():
            self.show_pass = not self.show_pass
            self.token_entry.configure(show="" if self.show_pass else "*")
            self.eye_btn.configure(text="🙈" if self.show_pass else "👁")
            
        self.eye_btn = ctk.CTkButton(self.token_frame, text="👁", width=40, height=35, fg_color=("#E4E4E7", "#48484A"), hover_color=("#D4D4D8", "#3A3A3C"), text_color=("#18181B", "white"), corner_radius=10, command=toggle_pass)
        self.eye_btn.pack(side="left")
        
        # Local Config
        self.local_frame = ctk.CTkFrame(self.cfg_frame, fg_color="transparent")
        
        self.path_container = ctk.CTkFrame(self.local_frame, fg_color="transparent")
        self.path_container.pack(pady=5)
        
        self.path_entry = ctk.CTkEntry(self.path_container, width=220, height=35, border_color=("#D4D4D8", "#3A3A3C"), fg_color=("#FFFFFF", "#18181A"), placeholder_text="Model Directory", corner_radius=10, text_color=("#18181B", "white"))
        self.path_entry.insert(0, settings["model_path"])
        self.path_entry.pack(side="left", padx=(0, 5))
        
        self.browse_btn = ctk.CTkButton(self.path_container, text="...", width=45, height=35, fg_color=("#E4E4E7", "#48484A"), hover_color=("#D4D4D8", "#3A3A3C"), text_color=("#18181B", "white"), corner_radius=10, command=self.browse_folder)
        self.browse_btn.pack(side="left")
        
        self.setup_btn = ctk.CTkButton(self.cfg_frame, text="DOWNLOAD OFFLINE ENGINE", font=ctk.CTkFont(size=13, weight="bold"), height=45, fg_color="#10A37F", hover_color="#0E906F", border_width=0, text_color="white", corner_radius=12, command=self.download_model)
        self.progress = ctk.CTkProgressBar(self.cfg_frame, progress_color="#10A37F", fg_color=("#E4E4E7", "#27272A"))
        self.progress.set(0)
        
        # --- Premium UI Buttons ---
        self.quit_btn = ctk.CTkButton(self.main_frame, text="QUIT APP", font=ctk.CTkFont(size=14, weight="bold"), height=45, fg_color="#EF4444", hover_color="#DC2626", border_width=0, text_color="white", corner_radius=12, command=self.quit_app)
        self.quit_btn.pack(side="bottom", pady=(5, 35), padx=40, fill="x")
        
        self.toggle_btn = ctk.CTkButton(self.main_frame, text="START LISTENING", font=ctk.CTkFont(size=15, weight="bold"), height=45, fg_color="#10A37F", hover_color="#0E906F", border_width=0, text_color="white", corner_radius=12, command=toggle_listening)
        self.toggle_btn.pack(side="bottom", pady=5, padx=40, fill="x")
        
        self.save_btn = ctk.CTkButton(self.main_frame, text="SAVE SETTINGS", font=ctk.CTkFont(size=14, weight="bold"), height=45, fg_color="#F59E0B", hover_color="#D97706", border_width=0, text_color="white", corner_radius=12, command=self.save_settings_btn)
        self.save_btn.pack(side="bottom", pady=(10, 5), padx=40, fill="x")
        
        # --- Make entire background draggable ---
        drag_widgets = [
            self, self.main_frame, self.logo_label, self.status_lbl, 
            self.cfg_frame, self.remote_frame, self.local_frame, 
            self.token_frame, self.path_container
        ]
        for w in drag_widgets:
            w.bind("<ButtonPress-1>", start_move)
            w.bind("<B1-Motion>", do_move)
            
        self.on_conn_change(settings["connection_mode"])
        
        keyboard.add_hotkey(HOTKEY_TOGGLE, toggle_listening, suppress=True)
        keyboard.add_hotkey(HOTKEY_BANGLA, lambda: set_mode_hotkey("Bangla"), suppress=True)
        keyboard.add_hotkey(HOTKEY_BANGLISH, lambda: set_mode_hotkey("Banglish"), suppress=True)
        
    def setup_tray_icon(self):
        global tray_icon
        def set_mode(icon, item):
            mode = item.text.split(" ")[0]
            set_mode_hotkey(mode)
        
        def is_checked(item):
            return settings["typing_mode"] == item.text.split(" ")[0]
            
        def tray_toggle_listening(icon, item):
            toggle_listening()
            
        def is_listening_checked(item):
            return is_listening
            
        menu = pystray.Menu(
            pystray.MenuItem("Toggle Microphone (Alt+V)", tray_toggle_listening, default=True, checked=is_listening_checked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", self.show_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Bangla (Alt+1)", set_mode, radio=True, checked=is_checked),
            pystray.MenuItem("Banglish (Alt+2)", set_mode, radio=True, checked=is_checked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit_app)
        )
        tray_icon = pystray.Icon("Bakkorup", base_logo_d_img, "বাক্যরূপ", menu)
        threading.Thread(target=tray_icon.run, daemon=True).start()
        update_tray_icon()

    def on_conn_change(self, mode):
        self.save_settings()
        self.remote_frame.pack_forget()
        self.local_frame.pack_forget()
        self.setup_btn.pack_forget()
        self.progress.pack_forget()
        
        if mode == "Remote":
            self.remote_frame.pack(fill="x", pady=5)
            self.update_status("Connecting to Remote...", ("#636366", "#8E8E93"))
        else:
            self.local_frame.pack(fill="x", pady=5)
            full_model_dir = os.path.join(settings["model_path"], MODEL_FOLDER_NAME)
            if not os.path.exists(full_model_dir) or not glob.glob(f"{full_model_dir}/*.onnx"):
                self.setup_btn.pack(pady=(10, 5), padx=40, fill="x")
                self.update_status("Offline Engine Missing", ("#D70015", "#FF453A"))
            else:
                self.update_status("Ready (Offline Mode)", ("#007A33", "#32D74B"))
            
    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=settings["model_path"])
        if folder:
            self.path_entry.delete(0, 'end')
            self.path_entry.insert(0, folder)
            self.save_settings()
            self.on_conn_change("Local")
        
    def download_model(self):
        self.setup_btn.configure(state="disabled", text="Downloading...")
        self.progress.pack(pady=10, padx=40, fill="x")
        
        def reporthook(count, block_size, total_size):
            if total_size > 0:
                percent = (count * block_size) / total_size
                self.after(10, lambda: self.progress.set(percent))
                
        def dl_thread():
            tar_name = MODEL_URL.split("/")[-1]
            dl_path = os.path.join(settings["model_path"], tar_name)
            urllib.request.urlretrieve(MODEL_URL, dl_path, reporthook)
            self.after(10, lambda: self.setup_btn.configure(text="Extracting..."))
            with tarfile.open(dl_path, "r:bz2") as tar:
                tar.extractall(path=settings["model_path"])
            os.remove(dl_path)
            self.after(10, lambda: self.setup_btn.pack_forget())
            self.after(10, self.progress.pack_forget)
            self.after(10, lambda: self.on_conn_change("Local"))
            
        threading.Thread(target=dl_thread, daemon=True).start()
        
    def load_settings(self):
        global settings
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                settings.update(json.load(f))
                if settings.get("typing_mode") == "English":
                    settings["typing_mode"] = "Bangla"
                
    def save_settings(self, *args):
        settings["typing_mode"] = self.mode_var.get() if hasattr(self, 'mode_var') else settings["typing_mode"]
        settings["connection_mode"] = self.conn_var.get() if hasattr(self, 'conn_var') else settings["connection_mode"]
        settings["remote_url"] = self.url_entry.get() if hasattr(self, 'url_entry') else settings["remote_url"]
        settings["auth_token"] = self.token_entry.get() if hasattr(self, 'token_entry') else settings["auth_token"]
        settings["model_path"] = self.path_entry.get() if hasattr(self, 'path_entry') else settings["model_path"]
        settings["theme"] = getattr(self, 'current_theme', settings.get("theme", "Dark"))
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
        if tray_icon:
            tray_icon.update_menu()
            
    def save_settings_btn(self):
        self.save_settings()
        self.update_status("Settings Saved", ("#007A33", "#32D74B"))
        
    def update_status(self, text, color):
        self.status_lbl.configure(text=f"Status: {text}", text_color=color)
        
    def hide_to_tray(self):
        self.withdraw()
        
    def show_from_tray(self):
        self.deiconify()
        self.force_taskbar()
        
    def force_taskbar(self):
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass
            
    def quit_app(self):
        self.save_settings()
        global tray_icon
        if tray_icon:
            tray_icon.stop()
        os._exit(0)

if __name__ == "__main__":
    global recognizer
    recognizer = None
    
    global app
    app = VoiceApp()
    app.setup_tray_icon()
    
    loop_thread = threading.Thread(target=start_asyncio_loop, daemon=True)
    loop_thread.start()
    
    app.mainloop()
