import config
import hikari
import lightbulb
import yt_dlp
import asyncio
import io
import tempfile
import os
import shutil

from urllib.parse import urlparse

MAX_VIDEO_LENGTH_MINUTES = 5
MAX_FILE_SIZE_MB = 25

bot = lightbulb.BotApp(
    token=config.DISCORD_TOKEN,
    intents=hikari.Intents.ALL
)

@bot.listen(hikari.GuildMessageCreateEvent)
async def print_message(e: hikari.MessageCreateEvent):
    if e.is_bot or e.message.channel_id != 1196126493336682608:
        return

    print(f"Processing message: {e.message.content}")
    
    result = await download_video_to_memory(e.message.content)

    # Handle error messages
    if isinstance(result, str):
        await e.message.respond(
            content=f"{e.author.mention} {result}",
            user_mentions=True
        )
        return
    
    video_bytes, filename = result
    size_mb = len(video_bytes) / (1024 * 1024)
    print(f"Downloaded {filename}, size: {size_mb:.2f} MB")
    
    # Check if file is too large
    if size_mb > MAX_FILE_SIZE_MB:
        await e.message.respond(
            content=f"{e.author.mention} Video is too large ({size_mb:.1f}MB). Discord limit is {MAX_FILE_SIZE_MB}MB.",
            user_mentions=True
        )
        return

    # Delete original message and send video
    await e.message.delete()
    await e.message.respond(
        content=f"{e.author.mention} <{e.message.content}>",
        user_mentions=True,
        attachment=hikari.Bytes(video_bytes, filename)
    )
    print("Video sent successfully")

def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and parsed.netloc != ""

async def download_video_to_memory(url: str):
    """Download video directly to memory and return (bytes, filename) or error string"""
    if not validate_url(url):
        return "Not A Valid Link"

    try:
        loop = asyncio.get_event_loop()
        
        def download_with_ydl():
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            
            try:
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'quiet': False,
                    'no_warnings': False,
                    'noplaylist': True,
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Get info and check duration
                    info = ydl.extract_info(url, download=False)
                    
                    duration = info.get('duration', 0)
                    if duration > 60 * MAX_VIDEO_LENGTH_MINUTES:
                        return None, f"Video Is Too Long. Max Length: {MAX_VIDEO_LENGTH_MINUTES} minutes"
                    
                    title = info.get('title', 'video')
                    ext = info.get('ext', 'mp4')
                    filename = f"{title}.{ext}"
                    
                    # Download the video
                    info = ydl.extract_info(url, download=True)
                    
                    # Get the actual downloaded file path
                    downloaded_path = ydl.prepare_filename(info)
                    
                    print(f"Downloaded to: {downloaded_path}")
                    
                    # Read file into memory
                    with open(downloaded_path, 'rb') as f:
                        video_bytes = f.read()
                    
                    return video_bytes, filename
                    
            finally:
                # Clean up temp directory and all files in it
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
        
        result = await loop.run_in_executor(None, download_with_ydl)
        
        if result[0] is None:
            return result[1]  # Error message
        
        return result  # (bytes, filename)
            
    except Exception as e:
        print(f"Error downloading video: {e}")
        import traceback
        traceback.print_exc()
        return "Something Went Wrong..."

bot.run()