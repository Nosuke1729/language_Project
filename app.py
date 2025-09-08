import streamlit as st

st.set_page_config(page_title="Language Project", page_icon="🌏")

st.title("Language Project")
st.write("ここにアプリの機能を少しずつ追加していきます。")

menu = st.sidebar.radio("メニュー", ["ホーム", "ユーザー情報", "チャット"])

if menu == "ホーム":
    st.subheader("ホーム")
    st.write("これはサンプルホーム画面です。")

elif menu == "ユーザー情報":
    st.subheader("ユーザー情報ページ")
    st.write("ここでユーザーの登録や表示を行います。")

elif menu == "チャット":
    st.subheader("チャットページ")
    st.write("ここでチャット機能を作ります。")
