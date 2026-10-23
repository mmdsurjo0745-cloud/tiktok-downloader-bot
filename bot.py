import asyncio
import os
import time
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
    await message.reply_text(
        "স্বাগতম! আমাকে যেকোনো **টিকটক** বা **ইনস্টাগ্রাম** ভিডিওর লিংক পাঠান।\n"
        "আমি সেটা **টেলিগ্রামের কোনো প্রকার কমপ্রেসন ছাড়া (Full HD)** ডাউনলোড করে দিব।"
    )

last_edit_time = 0

async def upload_progress(current, total, msg):
    global last_edit_time
    now = time.time()
    
    if now - last_edit_time > 3:
        last_edit_time = now
        percent = current * 100 / total
        bar_length = 15
        filled = int(bar_length * percent // 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        speed = current / (now - start_time) if (now - start_time) > 0 else 0
        speed_mb = speed / (1024 * 1024)
        
        try:
            await msg.edit_text(
                f"📤 ভিডিও আপলোড হচ্ছে (কমপ্রেসন ছাড়া)...\n"
                f"[{bar}] {percent:.1f}%\n"
                f"⚡ স্পিড: {speed_mb:.2f} MB/s"
            )
        except Exception:
            pass

@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def download_handler(client, message: Message):
    global start_time
    url = message.text.strip()
    
    is_tiktok = "tiktok.com" in url
    is_instagram = "instagram.com" in url
    
    if not (is_tiktok or is_instagram):
        await message.reply_text("দয়া করে একটি সঠিক টিকটক বা ইনস্টাগ্রাম ভিডিওর লিংক পাঠান।")
        return

    progress_data = {"status": "downloading", "percent": "0%", "method": "HD"}
    msg = await message.reply_text("⏳ অরিজিনাল HD ভিডিও ডাউনলোড হচ্ছে...\n[░░░░░░░░░░░░░░░] 0%")
    
    file_name = f"video_{message.from_user.id}.mp4"

    def download_logic():
        def ytdlp_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total_bytes > 0:
                    percent = int((downloaded / total_bytes) * 100)
                    progress_data["percent"] = f"{percent}%"

        ydl_opts = {
            # ফুল HD (1080p) এবং অডিও একসাথে ডাউনলোডের জন্য সেরা কনফিগারেশন
            'format': 'bestvideo*+bestaudio/best', 
            'outtmpl': file_name,
            'quiet': True,
            'no_warnings': True,
            'impersonate': 'chrome',
            'progress_hooks': [ytdlp_hook],
            # ইনস্টাগ্রাম ও টিকটকের জন্য অতিরিক্ত হেডার
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(file_name):
                return True
        except Exception as e:
            logger.warning(f"yt-dlp failed for {url}. Reason: {repr(e)}")
            
            if is_instagram:
                raise Exception("ইনস্টাগ্রাম ভিডিওটি ডাউনলোড করা যাচ্ছে না। (ইনস্টাগ্রাম মাঝে মাঝে বট ব্লক করে)")

        # TikWM API Fallback (শুধুমাত্র টিকটকের জন্য)
        if is_tiktok:
            progress_data["percent"] = "API Mode"
            progress_data["method"] = "TikWM"
            
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
        
        raise Exception("ভিডিও ডাউনলোড করা যায়নি।")

    async def update_progress():
        bar_length = 15
        last_text = ""
        while progress_data["status"] == "downloading":
            await asyncio.sleep(2.5)
            
            if progress_data["percent"].endswith("%"):
                percent_int = int(progress_data["percent"].replace("%", ""))
                filled = int(bar_length * percent_int // 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                text = f"⏳ ডাউনলোড হচ্ছে...\n[{bar}] {progress_data['percent']}"
            else:
                text = f"⏳ ভিডিও ডাউনলোড হচ্ছে ({progress_data['percent']})..."
            
            if text != last_text:
                try:
                    await msg.edit_text(text)
                    last_text = text
                except Exception:
                    pass

    try:
        progress_task = asyncio.create_task(update_progress())

        await asyncio.to_thread(download_logic)
        
        progress_data["status"] = "done"
        await progress_task

        start_time = time.time()
        await msg.edit_text("📤 ভিডিও আপলোড হচ্ছে (কমপ্রেসন ছাড়া)...\n[░░░░░░░░░░░░░░░] 0%")
        
        # ---------------------------------------------------------
        # 🔥 এখানে send_video এর বদলে send_document ব্যবহার করা হয়েছে 
        # যাতে টেলিগ্রাম একদমই ভিডিও কমপ্রেস না করে (Full HD নিশ্চিত)
        # ---------------------------------------------------------
        await client.send_document(
            chat_id=message.chat.id,
            document=file_name,
            caption="✅ আপনার ভিডিও ফুল HD (কমপ্রেসন ছাড়া) ডাউনলোড সম্পন্ন হয়েছে।",
            progress=upload_progress,
            progress_args=(msg,)
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
