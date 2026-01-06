# IG-chatbot-for-0412 (Python + Render + OpenRouter)

## Setup
1. Deploy as **Render → Web Service**
2. Environment variable:
   OPENROUTER_API_KEY=your_key_here
3. Build command:
   pip install -r requirements.txt
4. Start command:
   python app.py

## Rules
- Replies ONLY to one Instagram user ID
- No reply if self-harm or suicidal language appears
- You handle those messages manually

## Endpoint
POST /message

{
  "sender_id": "17842154490654283",
  "message": "text message",
  "recent_chat": [
    { "role": "assistant", "content": "previous reply" }
  ]
}
