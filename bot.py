import asyncio
import os
import logging
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

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...")
    file_name = f"video_{message.from_user.id}.mp4"

    try:
        # ব্লকিং কাজগুলো একটি আলাদা থ্রেডে চালানো হচ্ছে
        def download_hd_video():
            # TikWM API-তে HD রিকোয়েস্ট পাঠানো (hd=1)
            api_url = "https://www.tikwm.com/api/"
            payload = {"url": url, "hd": 1}
            response = requests.post(api_url, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"TikWM API Error: {data.get('msg', 'Unknown error')}")

            # HD লিংক নেওয়া, না পেলে সাধারণ প্লে লিংক
            video_info = data.get("data", {})
            video_url = video_info.get("hdplay") or video_info.get("play")
            
            if not video_url:
                raise Exception("ভিডিও লিংক পাওয়া যায়নি।")

            # ভিডিও ডাউনলোড
            video_res = requests.get(video_url, stream=True, timeout=60)
            video_res.raise_for_status()
            
            with open(file_name, 'wb') as f:
                for chunk in video_res.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True

        # asyncio.to_thread ব্যবহার করে ইভেন্ট লুপ ব্লক এড়ানো হচ্ছে
        await asyncio.to_thread(download_hd_video)

        # টেলিগ্রামে ভিডিও পাঠানো
        await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption="✅ আপনার ভিডিও ফুল HD কোয়ালিটিতে ডাউনলোড সম্পন্ন হয়েছে।"
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
