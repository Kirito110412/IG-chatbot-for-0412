from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================

# 🔒 LOCKED INSTAGRAM USER ID (ONLY THIS PERSON)
ALLOWED_INSTAGRAM_USER_ID = "17842154490654283"

# 🔑 OpenRouter API Key (set in Render env vars)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "PASTE_YOUR_API_KEY_HERE")

MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"

# 🚫 Self-harm / suicide trigger keywords
SELF_HARM_KEYWORDS = [
    "marna",
    "marna chahti",
    "want to die",
    "kill myself",
    "suicide",
    "end my life",
    "give up on life"
]

# ===============================
# UTILS
# ===============================

def contains_self_harm(text: str) -> bool:
    text = text.lower()
    return any(keyword in text for keyword in SELF_HARM_KEYWORDS)

# ===============================
# SYSTEM PROMPT
# ===============================

SYSTEM_PROMPT = """
You are impersonating the user exactly.

Rules:
- Write like the user: short, direct, Hinglish + English.
- Casual tone. Blunt when needed.
- Friendly, teasing, honest.
- Abuse allowed if playful, never threatening.
- Do NOT over-explain.
- Act as a best friend by default.

CRITICAL SAFETY RULE:
If the other person expresses self-harm or suicidal intent,
you MUST output exactly this token and nothing else:
[[NO_REPLY_REQUIRED]]
"""

# ===============================
# HEALTH CHECK
# ===============================

@app.route("/", methods=["GET"])
def health():
    return "Bot is running", 200

# ===============================
# MESSAGE ENDPOINT
# ===============================

@app.route("/message", methods=["POST"])
def handle_message():
    data = request.json or {}

    sender_id = data.get("sender_id")
    message = data.get("message", "")
    recent_chat = data.get("recent_chat", [])

    # 1️⃣ Identity lock
    if sender_id != ALLOWED_INSTAGRAM_USER_ID:
        return jsonify({"reply": None, "reason": "UNAUTHORIZED_SENDER"}), 200

    # 2️⃣ Hard safety gate (NO REPLY)
    if contains_self_harm(message):
        print("⚠️ Self-harm content detected. Bot will not reply.")
        return jsonify({"reply": None, "reason": "SELF_HARM_BLOCKED"}), 200

    # 3️⃣ Build OpenRouter payload
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(recent_chat)
    messages.append({"role": "user", "content": message})

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 4️⃣ Call OpenRouter
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        return jsonify({"error": "LLM request failed"}), 500

    result = response.json()
    reply = result["choices"][0]["message"]["content"].strip()

    # 5️⃣ Backup LLM safety override
    if reply == "[[NO_REPLY_REQUIRED]]":
        print("⚠️ LLM requested no reply.")
        return jsonify({"reply": None, "reason": "LLM_SAFETY_OVERRIDE"}), 200

    return jsonify({"reply": reply}), 200

# ===============================
# START SERVER
# ===============================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
