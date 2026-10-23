import asyncio
import os
import logging
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from rahad_all_downloader import alldl

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
    await message.reply_text("স্বাগতম! আমাকে যেকোনো টিকটক ভিডিওর লিংক পাঠান, আমি সেটা ওয়াটারমার্ক ছাড়া ডাউনলোড করে দিব।")

@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def download_handler(client, message: Message):
    url = message.text.strip()
    
    if "tiktok.com" not in url:
        await message.reply_text("দয়া করে একটি সঠিক টিকটক ভিডিও লিংক পাঠান।")
        return

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...")
    file_name = f"video_{message.from_user.id}.mp4"

    try:
        # TikWM API ভিত্তিক লাইব্রেরি থেকে ওয়াটারমার্ক ছাড়া ভিডিও লিংক নেওয়া
        result = alldl(url)
        video_url = result.get("videoUrl")
        
        if not video_url:
            raise Exception("ভিডিও লিংক পাওয়া যায়নি।")

        # সরাসরি ভিডিও ডাউনলোড
        response = requests.get(video_url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)

        # টেলিগ্রামে পাঠানো
        await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption="✅ আপনার ভিডিও ডাউনলোড সম্পন্ন হয়েছে।"
        )
        await msg.delete()

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await msg.edit_text(f"❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে।\n\nError: {str(e)}")
    finally:
        # ডাউনলোড শেষে সার্ভার থেকে ফাইল ডিলিট
        if os.path.exists(file_name):
            os.remove(file_name)

if __name__ == "__main__":
    print("বট চালু হচ্ছে...")
    app.run()
