import io
import os
import json
import requests

from PIL import Image
from fastapi import FastAPI, Request

from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
# from dotenv import load_dotenv

import google.generativeai as genai

# -----------------------
# Environment Variables
# -----------------------


# load_dotenv()
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_SECRET")
GEMINI_KEY = os.getenv("GEMINI_KEY")
GAS_URL = os.getenv("GAS_URL")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()

# -----------------------
# Google Sheet
# -----------------------

def save_to_google_sheet(data):

    print("SEND DATA TO SHEET:", data)

    try:
        response = requests.post(
            GAS_URL,
            json=data,
            timeout=20
        )

        print("SHEET RESPONSE:", response.status_code)
        print(response.text)

        if response.ok:
            return True

        print("Apps Script Error:", response.text)
        return False

    except Exception as e:
        print("REQUEST ERROR:", e)
        return False

# -----------------------
# LINE Event
# -----------------------

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):

    prompt = """
อ่านข้อความจากสลิปโอนเงินของธนาคาร SCB
ตอบเป็น JSON เท่านั้น
{
    "amount": "",
    "date": "YYYY-MM-DD",
    "time": "HH:mm",
    "receiver": "",
    "memo": "",
    "reference": ""
}

กฎ
- amount เป็นตัวเลข เช่น 1250.00
- date ต้องเป็น ค.ศ. เช่น 2025-06-30
- time ต้องเป็น HH:mm
- receiver คือชื่อผู้รับ
- memo คือข้อความบันทึก (ถ้าไม่มีให้เป็น "")
- reference คือเลขอ้างอิงรายการ (Reference No.) บนสลิป SCB
- ถ้าหา reference ไม่เจอ ให้เป็น ""

ห้ามตอบข้อความอื่น
"""
    try:

        message_content = line_bot_api.get_message_content(event.message.id)

        image = Image.open(io.BytesIO(message_content.content))

        response = model.generate_content([prompt, image])

        text = response.text.strip()

        if text.startswith("```"):
            text = (
                text.replace("```json","")
                    .replace("```","")
                    .strip()
            )

        result = json.loads(text)

        required = [
            "amount",
            "date",
            "time",
            "receiver",
            "memo",
            "reference"
        ]

        for key in required:
            result.setdefault(key, "")

        ok = save_to_google_sheet(result)

        if ok:
            reply = f"""✅ บันทึกสำเร็จ
    💰 {result['amount']} บาท
    👤 {result['receiver']}
    📝 {result['memo']}
    🔖 Ref: {result['reference']}
    """
        else:

            reply = "❌ เขียน Google Sheet ไม่สำเร็จ"
    except json.JSONDecodeError:

        print("Gemini Response:", text)
        reply = "❌ Gemini ตอบข้อมูลไม่ถูกต้อง"

    except Exception as e:
        print(e)
        reply = "⚠️ ระบบเกิดข้อผิดพลาด"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(reply)
    )


# -----------------------
# Webhook
# -----------------------

@app.post("/callback")
async def callback(request: Request):

    signature = request.headers.get(
        "X-Line-Signature"
    )

    body = await request.body()

    handler.handle(
        body.decode(),
        signature
    )

    return "OK"