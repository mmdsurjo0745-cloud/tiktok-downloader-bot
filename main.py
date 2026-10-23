import os
import staypresent

# Koyeb-এর হেলথ চেকের জন্য
staypresent.web.json({"status": "running"})

# আপনার বটের মূল ফাইল 'bot.py' কে চালু করা
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    staypresent.run("bot.py", port=port)
