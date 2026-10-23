import asyncio
import os
import logging
import yt_dlp
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

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...")
    file_name = f"video_{message.from_user.id}.mp4"

    try:
        # ব্লকিং কাজগুলো একটি আলাদা থ্রেডে চালানো হচ্ছে
        def download_video():
            ydl_opts = {
                # bestvideo+bestaudio/best ব্যবহার করলে সর্বোচ্চ রেজোলিউশন (HD) নিশ্চিত হয়
                'format': 'bestvideo+bestaudio/best', 
                'outtmpl': file_name,
                'quiet': True,
                'no_warnings': True,
                'impersonate': 'chrome', # curl_cffi ব্যবহার করে টিকটকের ব্লক এড়াবে
                # টিকটকের সবচেয়ে ভালো সার্ভার থেকে ডাটা আনতে সাহায্য করে
                'extractor_args': {'tiktok': {'api_hostname': ['api22-normal-c-useast2a.tiktokv.com']}}
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True

        # asyncio.to_thread ব্যবহার করে ইভেন্ট লুপ ব্লক এড়ানো হচ্ছে
        await asyncio.to_thread(download_video)

        # টেলিগ্রামে ভিডিও পাঠানো (supports_streaming=True দিলে টেলিগ্রাম কমপ্রেস করে না)
        await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption="✅ আপনার ভিডিও ফুল HD কোয়ালিটিতে ডাউনলোড সম্পন্ন হয়েছে।",
            supports_streaming=True 
        )
        await msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await msg.edit_text(f"❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে।\n\nError: {str(e)}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

if __name__ == "__main__":
    print("বট চালু হচ্ছে...")
    app.run()
