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
st.title("🌐 Language Learning Chat")

# =========================
# ユーザー登録 / ログイン
# =========================
if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.display_name = None

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
    
    # ルーム一覧を取得
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
            # ルーム一覧を再取得
            rooms_resp = supabase.table("rooms").select("*").execute()
            rooms = rooms_resp.data
            selected_room_name = room["name"]
        else:
            st.warning("ルーム名を入力してください。")

    # 選択されたルーム情報
    selected_room = next((r for r in rooms if r["name"] == selected_room_name), None)

    if selected_room is None:
        st.warning("選択されたルームが見つかりません。新しく作成してください。")
    else:
        st.subheader(f"Room: {selected_room_name} ({selected_room['language']})")

        # =========================
        # チャット機能
        # =========================
        if "messages" not in st.session_state:
            st.session_state.messages = []

        show_translation = st.checkbox("母語翻訳を表示", value=True)

        # モデルロード（軽量モデル）
        @st.cache_resource
        def load_model():
            tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
            model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")
            return tokenizer, model

        tokenizer, model = load_model()

        user_input = st.text_input("あなたのメッセージ:")
        if st.button("送信") and user_input:
            # メッセージをDBに保存
            supabase.table("messages").insert({
                "room_id": selected_room["id"],
                "user_id": st.session_state.user_id,
                "role": "user",
                "content": user_input,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            # AI応答生成
            inputs = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
            outputs = model.generate(inputs, max_length=100, pad_token_id=tokenizer.eos_token_id)
            bot_response = tokenizer.decode(outputs[:, inputs.shape[-1]:][0], skip_special_tokens=True)

            # AI応答をDBに保存
            supabase.table("messages").insert({
                "room_id": selected_room["id"],
                "role": "bot",
                "content": bot_response,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.messages.append({"role": "bot", "content": bot_response})

        # 過去メッセージ表示
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f"**あなた:** {msg['content']}")
            else:
                text = msg['content']
                if show_translation:
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
                    text += " _(母語訳: " + " ".join(translated_words) + ")_"

                st.markdown(f"**AI:** {text}")

        # =========================
        # 単語帳に追加
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

        # =========================
        # 単語帳（復習用）
        # =========================
        st.subheader("単語帳（復習用）")
        vocab_list = supabase.table("vocab")\
            .select("*")\
            .eq("user_id", st.session_state.user_id)\
            .eq("language", selected_room["language"])\
            .execute()
        for v in vocab_list.data:
            st.markdown(f"- {v['source_word']} → {v.get('target_word', '')}")
