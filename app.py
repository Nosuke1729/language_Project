import streamlit as st
import os
from supabase import create_client
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# =========================
# Supabase 接続
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# Streamlit UI 設定
# =========================
st.set_page_config(page_title="Language Learning Chat", layout="wide")

st.markdown("""
<style>
body { background-color: #f5f5f5; }
.chat-container { max-width: 700px; margin: auto; height: 60vh; overflow-y: auto; padding: 10px; background-color: #fff; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
.user-bubble { background-color:#007bff; color:white; padding:10px 15px; border-radius:15px; margin:5px 0; max-width:70%; text-align:right; float:right; clear:both; }
.bot-bubble { background-color:#e5e5ea; color:black; padding:10px 15px; border-radius:15px; margin:5px 0; max-width:70%; text-align:left; float:left; clear:both; }
.clear-both { clear:both; }
.input-container { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); max-width: 700px; width: 100%; display: flex; gap: 5px; }
input[type=text] { flex: 1; padding: 10px; border-radius: 20px; border: 1px solid #ccc; }
button { padding: 10px 20px; border-radius: 20px; background-color: #007bff; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

st.title("🌐 Language Learning Chat")

# =========================
# ユーザー登録 / ログイン
# =========================
if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.display_name = None
    st.session_state.messages = []

with st.sidebar:
    st.header("ユーザー情報")
    email = st.text_input("メール")
    display_name = st.text_input("表示名")
    mother_tongue = st.selectbox("母語", ["Japanese", "English", "Maori"])
    
    if st.button("ログイン / 登録"):
        resp = supabase.table("users").select("*").eq("email", email).execute()
        if resp.data:
            user = resp.data[0]
        else:
            user = supabase.table("users").insert({
                "email": email,
                "display_name": display_name,
                "mother_tongue": mother_tongue
            }).execute().data[0]
        st.session_state.user_id = user["id"]
        st.session_state.display_name = user["display_name"]
        st.success(f"ログインしました: {user['display_name']}")

# =========================
# ルーム選択 / 作成
# =========================
if st.session_state.user_id:
    st.header("学習ルーム")
    
    rooms_resp = supabase.table("rooms").select("*").execute()
    rooms = rooms_resp.data
    room_names = [r["name"] for r in rooms] if rooms else []

    selected_room_name = st.selectbox("既存ルーム選択", room_names) if room_names else ""
    create_new = st.text_input("新しいルームを作る場合は名前を入力")

    if st.button("ルーム作成"):
        if create_new:
            room = supabase.table("rooms").insert({
                "owner_user_id": st.session_state.user_id,
                "name": create_new,
                "language": "English"
            }).execute().data[0]
            st.success(f"ルーム作成: {room['name']}")
            selected_room_name = room["name"]
            rooms.append(room)
        else:
            st.warning("ルーム名を入力してください。")

    selected_room = next((r for r in rooms if r["name"] == selected_room_name), None)

    if selected_room is None:
        st.warning("選択されたルームが見つかりません。新しく作成してください。")
    else:
        st.subheader(f"Room: {selected_room_name} ({selected_room['language']})")
        show_translation = st.checkbox("母語翻訳を表示", value=True)

        # =========================
        # モデルロード（軽量化）
        # =========================
        if "model_loaded" not in st.session_state:
            with st.spinner("モデルをロード中..."):
                tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
                model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")
                st.session_state.tokenizer = tokenizer
                st.session_state.model = model
                st.session_state.model_loaded = True

        tokenizer = st.session_state.tokenizer
        model = st.session_state.model

        # =========================
        # メッセージ送信
        # =========================
        user_input = st.text_input("あなたのメッセージ:", key="chat_input")
        if st.button("送信") and user_input:
            # DB保存
            supabase.table("messages").insert({
                "room_id": selected_room["id"],
                "user_id": st.session_state.user_id,
                "role": "user",
                "content": user_input,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            # AI応答
            inputs = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
            outputs = model.generate(inputs, max_length=100, pad_token_id=tokenizer.eos_token_id)
            bot_response = tokenizer.decode(outputs[:, inputs.shape[-1]:][0], skip_special_tokens=True)

            supabase.table("messages").insert({
                "room_id": selected_room["id"],
                "role": "bot",
                "content": bot_response,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.messages.append({"role": "bot", "content": bot_response})

        # =========================
        # チャット表示
        # =========================
        chat_html = "<div class='chat-container'>"
        for msg in st.session_state.messages:
            role = msg["role"]
            text = msg["content"]
            if show_translation and role == "bot":
                words = text.split()
                translated_words = []
                for w in words:
                    resp = supabase.table("vocab")\
                        .select("target_word")\
                        .eq("source_word", w)\
                        .eq("language", selected_room["language"])\
                        .execute()
                    if resp.data:
                        translated_words.append(resp.data[0]["target_word"])
                    else:
                        translated_words.append(w)
                text += "<br><small style='color: gray;'>母語訳: " + " ".join(translated_words) + "</small>"

            if role == "user":
                chat_html += f"<div class='user-bubble'>{text}</div>"
            else:
                chat_html += f"<div class='bot-bubble'>{text}</div>"
        chat_html += "<div class='clear-both'></div></div>"

        st.markdown(chat_html, unsafe_allow_html=True)

        # =========================
        # 単語帳
        # =========================
        st.subheader("単語帳に追加")
        new_word = st.text_input("追加したい単語を入力", key="vocab_input")
        if st.button("単語を保存"):
            exists = supabase.table("vocab")\
                .select("*")\
                .eq("user_id", st.session_state.user_id)\
                .eq("source_word", new_word)\
                .eq("language", selected_room["language"])\
                .execute()
            if not exists.data:
                supabase.table("vocab").insert({
                    "user_id": st.session_state.user_id,
                    "source_word": new_word,
                    "target_word": "",
                    "language": selected_room["language"]
                }).execute()
                st.success(f"{new_word} を単語帳に追加しました")

        st.subheader("単語帳（復習用）")
        vocab_list = supabase.table("vocab")\
            .select("*")\
            .eq("user_id", st.session_state.user_id)\
            .eq("language", selected_room["language"])\
            .execute()
        for v in vocab_list.data:
            st.markdown(f"- {v['source_word']} → {v.get('target_word', '')}")
