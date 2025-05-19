
import streamlit as st
from streamlit_option_menu import option_menu
from openai import OpenAI
import tempfile
import base64
import os
import json
import math
import io
from pydub import AudioSegment

# 初始化 OpenAI
API_KEY = st.secrets["openai_key"]
client = OpenAI(api_key=API_KEY)

# 載入 prompt
with open("prompt.json", "r", encoding="utf-8") as f:
    prompt = json.load(f)

# 隱藏 footer 與 menu
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# 側邊選單
with st.sidebar:
    selected = option_menu(
        menu_title="Menu",
        options=["Record", "Upload", "Transcribe", "Summary", "Q&A"],
        icons=["mic", "upload", "book", "file-text", "chat-dots"],
        default_index=0
    )

# session state
if 'transcribe_text' not in st.session_state:
    st.session_state.transcribe_text = None
if 'summary' not in st.session_state:
    st.session_state.summary = None

# 處理大檔案（切片上傳）
def transcribe_large_audio(audio, chunk_length=20*60*1000):
    full_transcript = ""

    chunks = math.ceil(len(audio) / chunk_length)

    for i in range(chunks):
        chunk = audio[i*chunk_length:(i+1)*chunk_length]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            chunk.export(tmp.name, format="mp3")
            with open(tmp.name, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text"
                )
                full_transcript += transcript + "\n"
            os.unlink(tmp.name)

    return full_transcript.strip()

# summarize
def summarize_text(text):
    messages = prompt + [{"role": "user", "content": text}]
    res = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )
    return res.choices[0].message.content

# Record 頁面
if selected == "Record":
    st.title("🎤 即時錄音系統")
    audio_file = st.audio_input("點擊下方按鈕錄音", key="recorder")
    AUDIO = audio_file

    if audio_file is not None:
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format="audio/wav")

        b64 = base64.b64encode(audio_bytes).decode()
        href = f'<a href="data:audio/wav;base64,{b64}" download="recording.wav">📥 下載錄音</a>'
        st.markdown(href, unsafe_allow_html=True)

# Upload 頁面
if selected == "Upload":
    st.title("📁 上傳音檔")
    uploaded = st.file_uploader("支援 MP3/WAV/MP4", type=["mp3", "wav", "mp4"])
    AUDIO = uploaded

    if uploaded:
        st.audio(uploaded)
        st.success("✅ 上傳成功，請前往 Transcribe 頁面")

# Transcribe 頁面
if selected == "Transcribe":
    st.title("📝 逐字稿")
    if 'audio_path' not in st.session_state:
        st.warning("請先錄音或上傳音檔")
    else:
        if st.button("🎧 開始轉譯"):
            with st.spinner("轉譯中，請稍候..."):
                transcript = transcribe_large_audio(AUDIO)
                st.session_state.transcribe_text = transcript
                st.success("✅ 轉譯完成！")

    if st.session_state.transcribe_text:
        st.text_area("逐字稿內容", st.session_state.transcribe_text, height=400)

# Summary 頁面
if selected == "Summary":
    st.title("🧾 摘要")
    if st.session_state.transcribe_text is None:
        st.warning("請先完成轉譯")
    else:
        if st.button("🧠 產生摘要"):
            with st.spinner("生成中..."):
                summary = summarize_text(st.session_state.transcribe_text)
                st.session_state.summary = summary
                st.success("✅ 摘要完成！")

    if st.session_state.summary:
        st.markdown(st.session_state.summary)

# Q&A 頁面
if selected == "Q&A":
    st.title("❓ 問答系統")
    if st.session_state.transcribe_text is None:
        st.warning("請先完成轉譯")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "system", "content": "你是一位會議助理，根據逐字稿回答問題。"},
                {"role": "user", "content": st.session_state.transcribe_text}
            ]

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if question := st.chat_input("請輸入問題"):
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=st.session_state.messages
                )
                reply = response.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
