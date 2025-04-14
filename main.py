import config
import hikari
import lightbulb
import yt_dlp
import uuid
import os
import time
import asyncio

from threading import Thread
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

MAX_VIDEO_LENGTH_MINUTES = 5

bot = lightbulb.BotApp(
    token=config.DISCORD_TOKEN,
    intents=hikari.Intents.ALL
    )

@bot.listen(hikari.GuildMessageCreateEvent)
async def print_message(e: hikari.MessageCreateEvent):
    if e.is_bot:
        return
    
    if e.message.channel_id != 1196126493336682608:
        return

    result = await download_video(e.message.content)

    # Sends an error message instead
    if not os.path.isfile(result):
        await e.message.respond(result)
        return
    

    # Check size and compress if needed
    size_mb = os.path.getsize(result) / (1024 * 1024)
    if size_mb > 8:
        await e.message.respond("Compressing video...")
        compressed_path = await compress_video(result)
        if compressed_path:
            os.remove(result)
            result = compressed_path

    await e.message.delete() # Deletes the original message

    await e.message.respond(
        content=f"{e.author.mention} <{e.message.content}>", 
        user_mentions=True,
        attachment=result
        )
    

def validateURL(url: str) -> bool:
    parsed_url = urlparse(url)
    
    has_valid_scheme = parsed_url.scheme == "http" or parsed_url.scheme == "https"

    has_netloc = parsed_url.netloc != ""

    if has_valid_scheme and has_netloc:
        return True
    else:
        return False
    
async def download_video(url: str):
    if not validateURL(url):
        return "Not A Valid Link"

    try:
        unique_id = str(uuid.uuid4())
        folder = "videos/"
        os.makedirs(folder, exist_ok=True) # Creates the folder if it doesn't exist

        # These placeholder values will be filled in my ydl once the video is downloaded
        title_placeholder = "%(title)s"
        extension_placeholder = "%(ext)s"

        # Create the output template with regular string concatenation
        # Creates the directory and file name of the video
        output_file = folder + title_placeholder + " " + unique_id + "." + extension_placeholder
        
        ydl_opts = {
            # 'cookiefile': "cookies.txt",
            'outtmpl': output_file,
            'format': 'best',
            'quiet': True,
            'noplaylist': True,  # Only allow single videos
            'proxy': config.PROXY_ADDRESS,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First get info without downloading
            info = ydl.extract_info(url, download=False)
            video_length = info.get('duration')
            
            # Check video length
            if video_length > 60 * MAX_VIDEO_LENGTH_MINUTES:
                return f"Video Is Too Long. Max Length: {MAX_VIDEO_LENGTH_MINUTES} minutes"
            
            # If length is OK, proceed with download using the same info
            ydl.process_info(info) # This call actually triggers the download
            filename = ydl.prepare_filename(info)
            
            # Get clean filename without temporary .part extension
            final_filename = filename.replace('.part', '') if '.part' in filename else filename
            if os.path.exists(filename):
                os.rename(filename, final_filename)

            delete_file_after_delay(final_filename)
            return final_filename
            
    except Exception as e:
        return "Something Went Wrong..."

def delete_file_after_delay(file_path: str):
    delay_minutes = 10
    
    def _delete_file():
        time.sleep(delay_minutes * 60)  # Convert minutes to seconds
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                print(f"Deleted file: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    # Start the deletion thread
    Thread(target=_delete_file, daemon=True).start()

async def compress_video(input_path):
    output_path = input_path.replace(".mp4", "_compressed.mp4")
    # Use ffmpeg to compress (you'll need ffmpeg installed)
    # proc = await asyncio.create_subprocess_exec(
    #     "ffmpeg", 
    #     "-i", input_path,       # Input file
    #     "-vcodec", "libx264",   # Video codec
    #     "-crf", "30",           # Constant Rate Factor (quality)
    #     "-preset", "veryfast",      # Encoding speed/compression tradeoff
    #     output_path             # Output file
    # )

    proc = await asyncio.create_subprocess_exec(
    "ffmpeg",
    "-i", input_path,          # Input file
    "-r", "30",                 # Framerate
    "-vcodec", "libx264",     
    "-crf", "24",             # Quality (18-28 range)
    "-preset", "fast",        # Good encoding speed
    "-movflags", "+faststart",
    "-profile:v", "main",     
    "-pix_fmt", "yuv420p",    
    "-vf", "scale=-2:720",    # Downscale to 720p
    "-acodec", "aac",         # Audio codec
    "-b:a", "64k",           # Audio bitrate
    output_path
    )

    await proc.wait()
    return output_path if proc.returncode == 0 else None

bot.run()