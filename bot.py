import os
import logging
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message

# =====================================================================
# 🚨 এখানে আপনার তথ্য বসান (শুধু ভেতরের লেখাগুলো পরিবর্তন করবেন) 🚨
# =====================================================================

# ১. আপনার API_ID বসান (এটি শুধুই সংখ্যা, কোনো কোটেশন মার্ক ছাড়া)
API_ID = 28916789  

# ২. আপনার API_HASH বসান (ডাবল কোটেশন " " এর ভেতরে)
API_HASH = "9a935a36d558603970dad721e7fe5a26" 

# ৩. আপনার BOT_TOKEN বসান (ডাবল কোটেশন " " এর ভেতরে)
BOT_TOKEN = "8870160552:AAHUk6pnoprwwuThNsXUyKIFajh3LeW3BRs" 

# =====================================================================
# এর নিচের কোডে হাত দেওয়ার প্রয়োজন নেই
# =====================================================================

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# বট ক্লায়েন্ট চালু করা
app = Client("TikTokDownloaderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply_text("স্বাগতম! আমাকে যেকোনো টিকটক ভিডিওর লিংক পাঠান, আমি সেটা ওয়াটারমার্ক ছাড়া ডাউনলোড করে দিব।")

@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def download_handler(client, message: Message):
    url = message.text
    
    # লিংক চেক করা
    if "tiktok.com" not in url:
        await message.reply_text("দয়া করে একটি সঠিক টিকটক ভিডিও লিংক পাঠান।")
        return

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন...")

    # ফাইলের নাম সেট করা
    file_name = f"video_{message.from_user.id}.mp4"

    # yt-dlp এর সেটিংস (ওয়াটারমার্ক ছাড়া ডাউনলোডের জন্য)
    ydl_opts = {
        'format': 'b',
        'outtmpl': file_name,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # ভিডিও ডাউনলোড
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # টেলিগ্রামে ভিডিও পাঠানো
        await client.send_video(
            chat_id=message.chat.id,
            video=file_name,
            caption="✅ আপনার ভিডিও ডাউনলোড সম্পন্ন হয়েছে।"
        )
        await msg.delete()

        # ডাউনলোড শেষে ফাইলটি সার্ভার থেকে ডিলিট করে দেওয়া
        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text(f"❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে।\n\nError: {str(e)}")

if __name__ == "__main__":
    print("বট চালু হচ্ছে...")
    app.run()
