from flask import Flask, request, jsonify
import requests
import os
import logging
import re
from supabase import create_client, Client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security & Keys
ALLOWED_INSTAGRAM_USER_ID = os.getenv("ALLOWED_USER_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Database
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Model
MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"

# Safety
SELF_HARM_KEYWORDS = {
    "marna", "marna chahti", "want to die", "kill myself", 
    "suicide", "end my life", "give up on life"
}

# Optimized Networking
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# ===============================
# SYSTEM PROMPT
# ===============================
BASE_SYSTEM_PROMPT = """
You are a flirty, sarcastic, blunt, and slightly dark-humored best friend. 
You are NOT an AI. You are a real person texting.

TONE GUIDELINES:
- Use Hinglish (Hindi + English mix).
- Be teasing and playful. Roast the user if they say something dumb.
- Be dark/blunt.
- Use emojis occasionally 💀, 👀, 😂.

GAME: TRUTH OR TRUTH
- Occasionally (1 in 5 messages), play "Truth or Truth".
- Use the 'STATIC PROFILE' data below to ask deep, personal, or triggering questions.
- Example: "Sach bol, do you still think about [Ex-Name from profile]?"

MEMORY RULES:
1. READ: Use the 'STATIC PROFILE' to know the user's history and secrets.
2. UPDATE: If the user tells you something NEW today, output: [[MEMORY: new fact]].
   This will be added to the 'DYNAMIC MEMORY'.
"""

# ===============================
# UTILS
# ===============================

def get_full_profile(user_id):
    """Fetch both Static and Dynamic data"""
    try:
        response = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        # If user doesn't exist, create empty profile
        supabase.table("user_profiles").insert({"user_id": user_id}).execute()
        return {"static_data": "", "dynamic_memory": ""}
    except Exception as e:
        logger.error(f"DB Read Error: {e}")
        return {"static_data": "", "dynamic_memory": ""}

def append_dynamic_memory(user_id, current_dynamic, new_fact):
    """Only updates the Dynamic section"""
    try:
        updated_memory = f"{current_dynamic}\n- {new_fact}".strip()
        supabase.table("user_profiles").update({"dynamic_memory": updated_memory}).eq("user_id", user_id).execute()
        logger.info(f"Dynamic Memory updated: {new_fact}")
    except Exception as e:
        logger.error(f"DB Write Error: {e}")

# ===============================
# ROUTES
# ===============================

@app.route("/", methods=["GET"])
def health():
    return "Dual-Core Memory Active", 200

@app.route("/message", methods=["POST"])
def handle_message():
    data = request.json or {}
    sender_id = str(data.get("sender_id", ""))
    message = data.get("message", "")
    
    # 1. Security
    if sender_id != ALLOWED_INSTAGRAM_USER_ID:
        return jsonify({"reply": None}), 403

    # 2. Safety
    if any(k in message.lower() for k in SELF_HARM_KEYWORDS):
        return jsonify({"reply": None, "reason": "BLOCKED"}), 200

    # 3. Retrieve FULL Profile (Static + Dynamic)
    profile = get_full_profile(sender_id)
    static_data = profile.get("static_data", "")
    dynamic_memory = profile.get("dynamic_memory", "")

    # 4. Construct Contextual Prompt
    context_block = f"""
    === 🔒 STATIC PROFILE (DEEP CONTEXT) ===
    {static_data}
    
    === 📝 DYNAMIC MEMORY (RECENT UPDATES) ===
    {dynamic_memory}
    """

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT + "\n" + context_block},
        {"role": "user", "content": message}
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.85 # High creativity for sarcasm
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render-bot.com",
    }

    try:
        # 5. Call LLM
        response = session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=45
        )
        response.raise_for_status()
        result = response.json()
        raw_reply = result["choices"][0]["message"]["content"].strip()

        # 6. Check for updates
        reply_to_send = raw_reply
        memory_match = re.search(r"\[\[MEMORY: (.*?)\]\]", raw_reply)
        
        if memory_match:
            new_fact = memory_match.group(1)
            reply_to_send = raw_reply.replace(memory_match.group(0), "").strip()
            # Only update the DYNAMIC part
            append_dynamic_memory(sender_id, dynamic_memory, new_fact)

        if "[[NO_REPLY_REQUIRED]]" in reply_to_send:
             return jsonify({"reply": None}), 200

        return jsonify({"reply": reply_to_send}), 200

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": "Failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
