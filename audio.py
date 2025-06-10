import discord
from discord.ext import commands
import os
import urllib.parse
import tempfile
import requests
import matplotlib.pyplot as plt
import numpy as np
import librosa
import librosa.display
from pydub.utils import mediainfo
import io
from dotenv import load_dotenv

# === DISCORD CONFIG ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="&", intents=intents)

# === Dropbox Helpers ===
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

def extract_filename_from_url(url):
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    return os.path.basename(path)

def dropbox_direct_url(shared_url):
    return shared_url.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("?dl=0", "").replace("?dl=1", "")

def download_from_dropbox(dropbox_url, dest_path):
    url = dropbox_direct_url(dropbox_url)
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise Exception(f"Failed to download file: {r.status_code}")
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

# === Spectrogram Generator (In-Memory) ===

def generate_spectrogram_to_memory(audio_path, title_filename):
    info = mediainfo(audio_path)
    sample_rate = info.get("sample_rate", "Unknown")
    bit_depth = info.get("bits_per_sample", "Unknown")
    channels = info.get("channels", "1")
    bitrate = info.get("bit_rate", None)
    bitrate_str = f"{int(bitrate) // 1000} kbps" if bitrate else "Unknown bitrate"
    format_info = f"{sample_rate} Hz, {bit_depth} bits, channel {channels}"

    y, sr = librosa.load(audio_path, sr=None)
    S = librosa.stft(y, n_fft=4096, hop_length=512)
    S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)

    # Styling
    plt.style.use('dark_background')
    plt.rcParams.update({
        'axes.facecolor': 'black',
        'figure.facecolor': 'black',
        'axes.edgecolor': 'white',
        'axes.labelcolor': 'white',
        'xtick.color': 'white',
        'ytick.color': 'white',
        'text.color': 'white',
        'axes.titlecolor': 'white',
        'savefig.facecolor': 'black',
        'savefig.edgecolor': 'black',
        'font.family': 'monospace',
    })

    fig, ax = plt.subplots(figsize=(10, 5))
    img = librosa.display.specshow(S_db, sr=sr, hop_length=512, x_axis='time', y_axis='linear', cmap='plasma', ax=ax)

    # Dynamic frequency axis
    nyquist = sr // 2
    step_khz = 2000
    freqs = np.arange(0, nyquist + 1, step_khz)
    ax.set_ylim(0, nyquist)
    ax.set_yticks(freqs)
    ax.set_yticklabels([f"{f // 1000} kHz" if f >= 1000 else f"{f} Hz" for f in freqs])

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")

    # Add dB colorbar
    cbar = fig.colorbar(img, ax=ax, format="%+2.0f dB")
    cbar.set_label("Amplitude (dB)", color='white')
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.get_yticklabels(), color='white')

    # Add title with full margin
    fig.suptitle(
        f"{title_filename}\nStream 1 / 1: PCM {format_info}, {bitrate_str}",
        fontsize=10, ha='left', x=0.01, y=1.05
    )

    # Manual layout adjustment (prevents cutoff)
    fig.subplots_adjust(left=0.15, right=0.95, top=0.85, bottom=0.12)

    # Save to memory
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return buffer

# === Discord Command ===

@bot.command()
async def checktrack(ctx, dropbox_link: str):
    print("Analysis on " + dropbox_link)
    await ctx.send("Generating Image - Please wait...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_audio = os.path.join(tmpdir, "audio.wav")
            filename = extract_filename_from_url(dropbox_link)

            download_from_dropbox(dropbox_link, local_audio)

            if not filename.lower().endswith(".wav"):
                await ctx.send("❌ Only `.wav` files are supported right now.")
                return

            image_buffer = generate_spectrogram_to_memory(local_audio, filename)

            discord_file = discord.File(fp=image_buffer, filename=f"{filename}_spectrogram.png")
            await ctx.send(
            content=f"✅ {ctx.author.mention}, here's your spectrogram:",
            file=discord.File(fp=image_buffer, filename=f"{filename}_spectrogram.png")
)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Get the correct port from the environment
PORT = int(os.environ.get("PORT", 10000))  # fallback to 10000 if not set

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running.")

def run_dummy_server():
    server = HTTPServer(("0.0.0.0", PORT), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# === Start Bot ===
bot.run(TOKEN)



