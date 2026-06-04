import os
import sys
import glob
import json
import asyncio
import numpy as np
import uvicorn
import urllib.request
import tarfile
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query

app = FastAPI()

SAMPLE_RATE = 16000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "sherpa-onnx-streaming-zipformer-bn-vosk-2026-02-09")
# AUTH_TOKEN = os.getenv("VOSK_AUTH_TOKEN", "my_secret_token_123")  # Removed to respect Universal Gateway architecture
MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bn-vosk-2026-02-09.tar.bz2"

if not os.path.isdir(MODEL_DIR):
    print(f"Model directory '{MODEL_DIR}' not found. Downloading automatically...")
    tar_name = MODEL_URL.split("/")[-1]
    tar_path = os.path.join(BASE_DIR, tar_name)
    
    def reporthook(count, block_size, total_size):
        if total_size > 0:
            percent = int((count * block_size * 100) / total_size)
            sys.stdout.write(f"\rDownloading model... {percent}%")
            sys.stdout.flush()
            
    urllib.request.urlretrieve(MODEL_URL, tar_path, reporthook)
    print("\nDownload complete. Extracting...")
    with tarfile.open(tar_path, "r:bz2") as tar:
        tar.extractall(path=BASE_DIR)
    os.remove(tar_path)
    print("Extraction complete!")

try:
    encoder_file = glob.glob(f"{MODEL_DIR}/encoder*.onnx")[0]
    decoder_file = glob.glob(f"{MODEL_DIR}/decoder*.onnx")[0]
    joiner_file = glob.glob(f"{MODEL_DIR}/joiner*.onnx")[0]
    tokens_file = f"{MODEL_DIR}/tokens.txt"
except IndexError:
    print(f"ERROR: Could not find encoder/decoder/joiner .onnx files in {MODEL_DIR}")
    sys.exit(1)

print("Loading Sherpa-ONNX Zipformer model on CPU...")
import sherpa_onnx
recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
    encoder=encoder_file,
    decoder=decoder_file,
    joiner=joiner_file,
    tokens=tokens_file,
    num_threads=1,
    sample_rate=SAMPLE_RATE,
    feature_dim=80,
    enable_endpoint_detection=True,
    rule1_min_trailing_silence=1.2,
    rule2_min_trailing_silence=0.8,
    rule3_min_utterance_length=300,
)
print("Model loaded successfully! (Custom Bearer token authentication enabled)")
print("Ready to accept secure WebSocket connections.")

@app.get("/")
async def root():
    return {"status": "running", "message": "Bakkorup Voice Server is active."}

@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    # Native check removed. Gateway will handle security!
    # auth_header = websocket.headers.get("authorization", "")
    # if auth_header != f"Bearer {AUTH_TOKEN}":
    #     await websocket.close(code=1008, reason="Unauthorized")
    #     return
        
    await websocket.accept()
    stream = recognizer.create_stream()
    last_text = ""
    
    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message:
                audio_data = np.frombuffer(message["bytes"], dtype=np.int16).astype(np.float32) / 32768.0
                
                def process_audio():
                    nonlocal last_text
                    stream.accept_waveform(SAMPLE_RATE, audio_data)
                    while recognizer.is_ready(stream):
                        recognizer.decode_stream(stream)
                    
                    is_endpoint = recognizer.is_endpoint(stream)
                    current_text = recognizer.get_result(stream)
                    
                    res = []
                    if is_endpoint:
                        if current_text:
                            res.append({"type": "final", "text": current_text})
                        recognizer.reset(stream)
                        last_text = ""
                    elif current_text != last_text and current_text:
                        res.append({"type": "partial", "text": current_text})
                        last_text = current_text
                    return res
                
                results = await asyncio.to_thread(process_audio)
                
                for r in results:
                    await websocket.send_json(r)
                    
            elif "text" in message:
                data = json.loads(message["text"])
                if data.get("action") == "stop":
                    def flush_audio():
                        stream.accept_waveform(SAMPLE_RATE, [0.0] * int(SAMPLE_RATE * 0.1))
                        while recognizer.is_ready(stream):
                            recognizer.decode_stream(stream)
                        text = recognizer.get_result(stream)
                        recognizer.reset(stream)
                        return text
                        
                    final_text = await asyncio.to_thread(flush_audio)
                    if final_text:
                        await websocket.send_json({"type": "final", "text": final_text})
                    last_text = ""

    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Free the stream from memory when disconnected
        del stream

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    uvicorn.run(app, host="0.0.0.0", port=port, ws_ping_interval=None, ws_ping_timeout=None)
