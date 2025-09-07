from flask import Flask, render_template, request, jsonify
import os
from supabase import create_client
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# =========================
# Supabase 接続
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# Flask 設定
# =========================
app = Flask(__name__)

# モデルロード（軽量モデル）
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")

# =========================
# ルート
# =========================
@app.route("/")
def index():
    return render_template("index.html")

# =========================
# メッセージ送信API
# =========================
@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.json
    user_id = data.get("user_id")
    room_id = data.get("room_id")
    user_input = data.get("message")

    # DBに保存（ユーザー発言）
    supabase.table("messages").insert({
        "room_id": room_id,
        "user_id": user_id,
        "role": "user",
        "content": user_input,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    # AI応答生成
    inputs = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
    outputs = model.generate(inputs, max_length=100, pad_token_id=tokenizer.eos_token_id)
    bot_response = tokenizer.decode(outputs[:, inputs.shape[-1]:][0], skip_special_tokens=True)

    # DBに保存（AI応答）
    supabase.table("messages").insert({
        "room_id": room_id,
        "role": "bot",
        "content": bot_response,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    return jsonify({"bot_response": bot_response})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
