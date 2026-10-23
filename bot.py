import asyncio
import os
import logging
import yt_dlp
import requests
from pyrogram import Client, filters
from pyrogram.types import Message

# Render-এ Event Loop এরর এড়ানোর ফিক্স
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Render-এর Environment Variables থেকে তথ্য নেওয়া
API_ID = int(os.getenv("API_ID", "28916789"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("TikTokDownloaderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply_text("স্বাগতম! আমাকে যেকোনো টিকটক ভিডিওর লিংক পাঠান, আমি সেটা ওয়াটারমার্ক ছাড়া ফুল HD কোয়ালিটিতে ডাউনলোড করে দিব।")

@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def download_handler(client, message: Message):
    url = message.text.strip()
    
    if "tiktok.com" not in url:
        await message.reply_text("দয়া করে একটি সঠিক টিকটক ভিডিও লিংক পাঠান।")
        return

    # প্রোগ্রেস ট্র্যাকিং এর জন্য ডিকশনারি
    progress_data = {"status": "downloading", "percent": "0%", "method": "HD"}
    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...\n[░░░░░░░░░░░░░░░] 0%")
    
    file_name = f"video_{message.from_user.id}.mp4"

    def download_logic():
        # --- পদ্ধতি ১: yt-dlp ---
        def ytdlp_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total_bytes > 0:
                    percent = int((downloaded / total_bytes) * 100)
                    progress_data["percent"] = f"{percent}%"
                    progress_data["method"] = "yt-dlp"

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best', 
            'outtmpl': file_name,
            'quiet': True,
            'no_warnings': True,
            'impersonate': 'chrome',
            'progress_hooks': [ytdlp_hook],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(file_name):
                return True
        except Exception as e:
            logger.warning(f"yt-dlp failed, trying fallback API. Reason: {repr(e)}")

        # --- পদ্ধতি ২: TikWM API (Fallback) ---
        progress_data["percent"] = "API Mode"
        progress_data["method"] = "TikWM API"
        
        api_url = "https://www.tikwm.com/api/"
        payload = {"url": url, "hd": 1}
        response = requests.post(api_url, data=payload, timeout=30)
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"API Error: {data.get('msg')}")

        video_url = data.get("data", {}).get("hdplay") or data.get("data", {}).get("play")
        if not video_url:
            raise Exception("কোনো ভিডিও লিংক পাওয়া যায়নি।")

        video_res = requests.get(video_url, stream=True, timeout=60)
        video_res.raise_for_status()
        
        total_size = int(video_res.headers.get('content-length', 0))
        downloaded = 0
        
        with open(file_name, 'wb') as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        progress_data["percent"] = f"{percent}%"
        return True

    # প্রোগ্রেস আপডেট করার জন্য ব্যাকগ্রাউন্ড টাস্ক
    async def update_progress():
        bar_length = 15
        last_text = ""
        while progress_data["status"] == "downloading":
            await asyncio.sleep(2.5) # প্রতি আড়াই সেকেন্ড পর পর আপডেট হবে
            
            if progress_data["percent"].endswith("%"):
                percent_int = int(progress_data["percent"].replace("%", ""))
                filled = int(bar_length * percent_int // 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                text = f"⏳ ডাউনলোড হচ্ছে ({progress_data['method']})...\n[{bar}] {progress_data['percent']}"
            else:
                text = f"⏳ ভিডিও ডাউনলোড হচ্ছে ({progress_data['percent']})..."
            
            if text != last_text:
                try:
                    await msg.edit_text(text)
                    last_text = text
                except Exception:
                    pass # Ignore flood limits or message deletion

    try:
        # প্রোগ্রেস আপডেটার চালু করা
        progress_task = asyncio.create_task(update_progress())

        # মূল ডাউনলোড শুরু করা
        await asyncio.to_thread(download_logic)
        
        # ডাউনলোড শেষ হলে প্রোগ্রেস আপডেটার বন্ধ করা
        progress_data["status"] = "done"
        await progress_task

        # টেলিগ্রামে ভিডিও পাঠানো
        await msg.edit_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...")
        
        await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption=f"✅ আপনার ভিডিও ফুল HD কোয়ালিটিতে ডাউনলোড সম্পন্ন হয়েছে।",
            supports_streaming=True 
        )
        await msg.delete()

    except Exception as e:
        progress_data["status"] = "error"
        logger.error(f"Download Error: {repr(e)}")
        await msg.edit_text(f"❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে।\n\nError: {repr(e)}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

if __name__ == "__main__":
    print("বট চালু হচ্ছে...")
    app.run()
