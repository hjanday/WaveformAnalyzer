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
from imageio_ffmpeg import get_ffmpeg_exe
import soundfile as sf
from scipy.signal import stft

ffmpeg_path = get_ffmpeg_exe()
os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
# === DISCORD CONFIG ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="&", intents=intents)

# === Dropbox Helpers ===
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}", flush=True)

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
    print(f">>> File size: {os.path.getsize(dest_path)} bytes", flush=True)


# === Spectrogram Generator (In-Memory) ===

def generate_spectrogram_to_memory(audio_path, title_filename):
    # Metadata using pydub (still works for format info)
    info = mediainfo(audio_path)
    sample_rate = info.get("sample_rate", "Unknown")
    bit_depth = info.get("bits_per_sample", "Unknown")
    channels = info.get("channels", "1")
    bitrate = info.get("bit_rate", None)
    bitrate_str = f"{int(bitrate) // 1000} kbps" if bitrate else "Unknown bitrate"
    format_info = f"{sample_rate} Hz, {bit_depth} bits, channel {channels}"

    # Read audio data (no librosa)
    y, sr = sf.read(audio_path)
    if y.ndim > 1:
        y = y.mean(axis=1)  # convert to mono if stereo

    # Compute STFT
    f, t, Zxx = stft(y, fs=sr, nperseg=4096, noverlap=4096 - 512)
    S_db = 20 * np.log10(np.abs(Zxx) + 1e-6)  # amplitude to dB

    # Plotting
    import matplotlib
    matplotlib.use('Agg')  # headless backend
    import matplotlib.pyplot as plt

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
    img = ax.pcolormesh(t, f, S_db, shading='gouraud', cmap='plasma')
    ax.set_ylim(0, sr // 2)

    # Frequency ticks
    step_khz = 2000
    freqs = np.arange(0, (sr // 2) + 1, step_khz)
    ax.set_yticks(freqs)
    ax.set_yticklabels([f"{f // 1000} kHz" if f >= 1000 else f"{f} Hz" for f in freqs])

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")

    cbar = fig.colorbar(img, ax=ax, format="%+2.0f dB")
    cbar.set_label("Amplitude (dB)", color='white')
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.get_yticklabels(), color='white')

    fig.suptitle(
        f"{title_filename}\nStream 1 / 1: PCM {format_info}, {bitrate_str}",
        fontsize=10, ha='left', x=0.01, y=1.05
    )
    fig.subplots_adjust(left=0.15, right=0.95, top=0.85, bottom=0.12)

    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return buffer

# === Discord Command ===
@bot.command()
async def testcmd(ctx):
        await ctx.send(
      "hi"
)




@bot.command()
async def checktrack(ctx, dropbox_link: str):
    print(">>> checktrack command triggered", flush=True)
    print(f">>> ctx: {ctx}", flush=True)
    print(f">>> dropbox_link: {dropbox_link}", flush=True)
    await ctx.send("Generating Image - Please wait...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            print(">>> Temp directory created", flush=True)
            local_audio = os.path.join(tmpdir, "audio.wav")
            filename = extract_filename_from_url(dropbox_link)
            print(f">>> Extracted filename: {filename}", flush=True)

            download_from_dropbox(dropbox_link, local_audio)
            print(">>> File downloaded", flush=True)

            if not filename.lower().endswith(".wav"):
                print(">>> File not a .wav file", flush=True)
                await ctx.send("❌ Only `.wav` files are supported right now.")
                return

            print(">>> Generating spectrogram...", flush=True)
            image_buffer = generate_spectrogram_to_memory(local_audio, filename)
            print(">>> Spectrogram generated", flush=True)

            discord_file = discord.File(fp=image_buffer, filename=f"{filename}_spectrogram.png")
            await ctx.send(
                content=f"✅ {ctx.author.mention}, here's your spectrogram:",
                file=discord_file
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Error: {e}")

# === Start Bot ===
bot.run(TOKEN)



