from openai import OpenAI
from streamlit_option_menu import option_menu
import streamlit as st
import json
import base64
import tempfile
import os

# ======== 初始化與介面 ========
st.set_page_config(page_title="語音轉錄系統", layout="centered")

# 隱藏 Streamlit logo 與選單
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Sidebar 選單
with st.sidebar:
    selected = option_menu(
        menu_title="功能選單",
        menu_icon="mic",
        options=["Record", "Upload", "Transcribe", "Summary", "Q&A"],
        icons=["mic", "upload", "file-earmark-text", "chat-left-text", "question-circle"],
        default_index=0,
    )

# 讀取 prompt
with open('prompt.json', 'r', encoding='utf-8') as f:
    prompt_template = json.load(f)

# API Key 設定（從 Streamlit secrets）
API_Key = st.secrets["openai_key"]
client = OpenAI(api_key=API_Key)

# Session 初始化
if "transcription" not in st.session_state:
    st.session_state.transcription = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None

# ======== 錄音頁面 ========
if selected == "Record":
    st.title("🎤 即時錄音系統")
    st.markdown("使用下方錄音按鈕開始錄音，完成後可下載音訊檔。")

    audio_file = st.audio_input("請點擊開始錄音", key="audio_recorder")

    if audio_file:
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format="audio/wav")

        # 下載連結
        b64 = base64.b64encode(audio_bytes).decode()
        href = f'<a href="data:audio/wav;base64,{b64}" download="recording.wav">📥 下載錄音檔</a>'
        st.markdown(href, unsafe_allow_html=True)

# ======== 上傳頁面 ========
if selected == "Upload":
    st.title("📤 上傳音訊檔")

    uploaded_file = st.file_uploader("請上傳音訊檔", type=["mp3", "mp4", "wav"])
    if uploaded_file:
        st.audio(uploaded_file)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(uploaded_file.read())
            st.session_state.audio_path = tmp.name

        st.success("上傳成功！請切換至 Transcribe 進行語音辨識。")

# ======== 語音轉文字 ========
if selected == "Transcribe":
    st.title("📝 語音轉文字")
    if not st.session_state.audio_path:
        st.warning("請先至 Upload 頁面上傳音訊檔！")
    else:
        if st.button("🎙️ 開始辨識"):
            with st.spinner("辨識中..."):
                with open(st.session_state.audio_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="text"
                    )
                st.session_state.transcription = transcript
                st.success("語音辨識完成！")
        if st.session_state.transcription:
            st.text_area("🔍 辨識結果", st.session_state.transcription, height=300)

# ======== 摘要頁面 ========
if selected == "Summary":
    st.title("📄 摘要產生")
    if not st.session_state.transcription:
        st.warning("請先完成語音辨識！")
    else:
        if st.button("✏️ 開始摘要"):
            with st.spinner("摘要中..."):
                prompt_template[1]["content"] = st.session_state.transcription
                summary_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=prompt_template,
                    temperature=0.5
                )
                st.session_state.summary = summary_response.choices[0].message.content
                st.success("摘要完成！")

        if st.session_state.summary:
            st.markdown("### 📋 摘要內容")
            st.write(st.session_state.summary)

# ======== 問答頁面 ========
if selected == "Q&A":
    st.title("🤖 問答系統")

    if not st.session_state.transcription:
        st.warning("請先完成語音辨識！")
    else:
        preset_messages = [
            {"role": "system", "content": "你是一位助教，幫助用戶分析語音內容。"},
            {"role": "user", "content": st.session_state.transcription},
            {"role": "assistant", "content": "我已讀取語音內容，有什麼想問的嗎？"}
        ]

        if "messages" not in st.session_state:
            st.session_state.messages = preset_messages

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("請輸入你的問題"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                for response in client.chat.completions.create(
                    model="gpt-4",
                    messages=st.session_state.messages,
                    stream=True
                ):
                    full_response += response.choices[0].delta.get("content", "")
                    message_placeholder.markdown(full_response + "▌")

                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
