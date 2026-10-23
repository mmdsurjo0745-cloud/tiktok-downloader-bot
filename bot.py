import asyncio
import os
import time
import logging
import yt_dlp
import requests
import re
from deep_translator import GoogleTranslator
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
    
    video_title = "No Title"
    uploader_name = "Unknown User"
    download_source = "Unknown"

    def download_logic():
        nonlocal video_title, uploader_name, download_source
        
        def ytdlp_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total_bytes > 0:
                    percent = int((downloaded / total_bytes) * 100)
                    progress_data["percent"] = f"{percent}%"

        # 🚨 এখানে extractor_args যুক্ত করা হয়েছে যা টিকটকের ব্লক বাইপাস করে অরিজিনাল HD নামায়
        ydl_opts = {
            'format': 'bestvideo*+bestaudio/best', 
            'outtmpl': file_name,
            'quiet': True,
            'no_warnings': True,
            'impersonate': 'chrome',
            'progress_hooks': [ytdlp_hook],
            'extractor_args': {'tiktok': {'api_hostname': ['api22-normal-c-useast2a.tiktokv.com']}}
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                raw_title = info.get('title') or info.get('description')
                if raw_title and str(raw_title).strip():
                    video_title = str(raw_title).strip()[:100] 
                
                raw_uploader = info.get('uploader_id') or info.get('uploader') or info.get('channel')
                if raw_uploader and str(raw_uploader).strip():
                    uploader_name = str(raw_uploader).strip().replace("@", "")
                
                download_source = "yt-dlp (Original HD)"
                
            if os.path.exists(file_name):
                return True
        except Exception as e:
            logger.warning(f"yt-dlp failed for {url}. Reason: {repr(e)}")
            
            if is_instagram:
                raise Exception("ইনস্টাগ্রাম ভিডিওটি ডাউনলোড করা যাচ্ছে না।")

        # TikWM API Fallback (শুধুমাত্র টিকটকের জন্য)
        if is_tiktok:
            progress_data["percent"] = "API Mode"
            api_url = "https://www.tikwm.com/api/"
            payload = {"url": url, "hd": 1}
            response = requests.post(api_url, data=payload, timeout=30)
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"API Error: {data.get('msg')}")

            video_info = data.get("data", {})
            video_url = video_info.get("hdplay") or video_info.get("play")
            
            api_title = video_info.get("title")
            if api_title and str(api_title).strip():
                video_title = str(api_title).strip()[:100]

            author_info = video_info.get("author", {})
            api_uploader = author_info.get("unique_id") or author_info.get("nickname")
            if api_uploader and str(api_uploader).strip():
                uploader_name = str(api_uploader).strip().replace("@", "")

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
            
            download_source = "TikWM API (Fallback HD)"
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

        # টাইটেল ইংরেজিতে অনুবাদ
        try:
            translated_title = GoogleTranslator(source='auto', target='en').translate(video_title)
            if translated_title:
                video_title = translated_title
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
        safe_uploader = re.sub(r'[\\/*?:"<>|]', "", uploader_name)
        
        final_file_name = f"@{safe_uploader} - {safe_title[:30]}.mp4"
        
        start_time = time.time()
        await msg.edit_text("📤 ভিডিও আপলোড হচ্ছে (কমপ্রেসন ছাড়া)...\n[░░░░░░░░░░░░░░░] 0%")
        
        # ফাইল সাইজ বের করা MB তে
        file_size_mb = os.path.getsize(file_name) / (1024 * 1024)
        
        await client.send_document(
            chat_id=message.chat.id,
            document=file_name,
            file_name=final_file_name, 
            caption=f"✅ **ভিডিও ডাউনলোড সম্পন্ন**\n\n"
                    f"👤 **ইউজারনেম (ID):** @{uploader_name}\n"
                    f"📝 **টাইটেল:** {video_title}\n"
                    f"📦 **সাইজ:** {file_size_mb:.2f} MB\n"
                    f"⚙️ **সোর্স:** {download_source}",
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
