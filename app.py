import streamlit as st
import google.generativeai as genai
import subprocess
import os
import time
import re
import requests
from pydub import AudioSegment
from pydub.silence import split_on_silence
import tempfile

# --- Configurations ---
st.set_page_config(page_title="Super Subtitle Cloud ☁️", layout="wide")
st.markdown("""<style>.stButton>button {width: 100%; background-color: #007BFF; color: white; font-size: 18px; font-weight: bold;}</style>""", unsafe_allow_html=True)
st.title("🚀 Super Subtitle Cloud v12.0 ☁️")
st.info("ئەم وەشانە بەتەواوی لەسەر هەور کاردەکات. دەتوانیت لە مۆبایل و کۆمپیوتەر بەکاری بهێنیت.")

# --- API Key & Model Setup (Cloud Secure Method) ---
try:
    # کلیلی API لە بەشی نهێنییەکانی Streamlit Cloud وەردەگرێت
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
except Exception as e:
    st.error("❌ کێشەیەک لە وەرگرتنی کلیلی API هەیە. دڵنیابە لە بەشی Secrets لە Streamlit Cloud بە ناوی GEMINI_API_KEY کلیلی APIـەکەت داناوە.")
    st.stop()

# --- Helper Functions (Cloud Optimized) ---

def upload_to_gofile(file_path):
    st.write(f"☁️ ئەپڵۆدکردنی {os.path.basename(file_path)} بۆ GoFile...")
    try:
        #... (هەمان فەنکشنی GoFile لە وەڵامی پێشوو)
        server_response = requests.get("https://api.gofile.io/getServer", timeout=10)
        server_response.raise_for_status()
        server = server_response.json()["data"]["server"]
        with open(file_path, "rb") as f:
            files = {"file": f}
            upload_response = requests.post(f"https://{server}.gofile.io/uploadFile", files=files, timeout=60)
            upload_response.raise_for_status()
        upload_data = upload_response.json()
        if upload_data["status"] == "ok":
            st.success(f"✅ {os.path.basename(file_path)} بە سەرکەوتوویی ئەپڵۆد کرا.")
            return upload_data["data"]
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"هەڵەیەک لە کاتی ئەپڵۆدکردن بۆ GoFile ڕوویدا: {e}")
        return None

def split_audio_intelligently(audio_path, max_duration_minutes=14):
    #... (هەمان فەنکشنی دابەشکردنی دەنگ لە وەڵامی پێشوو)
    st.write("🔊 دابەشکردنی زیرەکانەی دەنگ لەسەر سێرڤەر...")
    try:
        audio = AudioSegment.from_file(audio_path)
        silent_chunks = split_on_silence(audio, min_silence_len=700, silence_thresh=audio.dBFS-14, keep_silence=300)
        max_duration_ms = max_duration_minutes * 60 * 1000
        output_chunks = []
        current_chunk = AudioSegment.empty()
        for chunk in silent_chunks:
            if len(current_chunk) + len(chunk) < max_duration_ms:
                current_chunk += chunk
            else:
                output_chunks.append(current_chunk)
                current_chunk = chunk
        if len(current_chunk) > 0:
            output_chunks.append(current_chunk)
        st.write(f"✅ دەنگەکە بۆ {len(output_chunks)} پارچەی زیرەکانە دابەش کرا.")
        return output_chunks
    except Exception as e:
        st.error(f"هەڵە لە دابەشکردنی دەنگ: {e}")
        return []

def generate_srt_with_retry(audio_file_uri, max_retries=3):
    #... (هەمان فەنکشنی Retry لە وەڵامی پێشوو)
    prompt = "تکایە ئەم دەنگە بکە بە ژێرنووسی SRT بە زمانی کوردی سۆرانی. پابەندی فۆرماتی ستانداردی HH:MM:SS,ms بە. ڕستەکان لەت مەکە و هەر ژێرنووسێک لە دێڕێکی جیاواز بنووسە."
    for attempt in range(max_retries):
        try:
            st.write(f"🧠 هەوڵی {attempt + 1}/{max_retries}: ناردنی داواکاری بۆ Gemini...")
            audio_file = genai.get_file(name=audio_file_uri)
            response = model.generate_content([audio_file, prompt], request_options={"timeout": 600})
            raw_srt = response.text.strip().replace("```srt", "").replace("```", "")
            if '-->' not in raw_srt:
                raise ValueError("فۆرماتی SRT هەڵەیە.")
            return raw_srt
        except Exception as e:
            st.warning(f"هەڵەیەک لە وەڵامی Gemini ڕوویدا (هەوڵی {attempt + 1}): {e}")
            if attempt < max_retries-1:
                prompt = "هەوڵی پێشوو سەرکەوتوو نەبوو. تکایە چاکی بکەوە و تەنها فایلێکی SRTـی ستاندارد بنێرە."
            else:
                st.error("نەتوانرا وەڵامێکی دروست لە Gemini وەربگیرێت.")
                return None
    return None
    
#... (هەموو فەنکشنەکانی تری وەک master_srt_repair_system و offset_srt_timestamps لێرە دابنێ)

def to_srt_time(total_seconds):
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds_float = divmod(remainder, 60)
    seconds = int(seconds_float)
    milliseconds = int((seconds_float - seconds) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:02d},{milliseconds:03d}"

def offset_srt_timestamps(srt_text, offset_seconds):
    lines = srt_text.strip().split('\n')
    new_lines = []
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[,.]\d{3}) --> (\d{2}:\d{2}:\d{2}[,.]\d{3})')
    def parse_time(t_str):
        t_str = t_str.replace(',', '.')
        h, m, s = map(float, t_str.split(':'))
        return h * 3600 + m * 60 + s
    for line in lines:
        match = time_pattern.search(line)
        if match:
            start_str, end_str = match.groups()
            start_time = parse_time(start_str) + offset_seconds
            end_time = parse_time(end_str) + offset_seconds
            new_lines.append(f"{to_srt_time(start_time)} --> {to_srt_time(end_time)}")
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)
    
def master_srt_repair_system(srt_text):
    # This function is from your original code, it's good for re-numbering and final cleanup
    def parse_time(t_str):
        try:
            t_str = t_str.strip().replace('.', ',')
            parts = t_str.split(',')
            hms_part = parts[0]
            ms = int(parts[1]) if len(parts) > 1 else 0
            time_parts = list(map(int, hms_part.split(':')))
            if len(time_parts) == 3: return time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2] + ms / 1000.0
            if len(time_parts) == 2: return time_parts[0] * 60 + time_parts[1] + ms / 1000.0
            return time_parts[0] + ms / 1000.0
        except: return 0.0

    parsed_blocks = []
    # Combine SRT blocks that were split across newlines
    srt_text_combined = re.sub(r'(\d+\n[\d:,->\s]+\n)([a-zA-Z\d])', r'\1\n\2', srt_text, flags=re.M)

    for block in srt_text_combined.strip().split('\n\n'):
        if not block.strip(): continue
        lines = block.split('\n')
        if len(lines) < 2 or '-->' not in lines[1]: continue
        try:
            start_str, end_str = [s.strip() for s in lines[1].split('-->')]
            start_sec = parse_time(start_str)
            end_sec = parse_time(end_str)
            text = '\n'.join(lines[2:])
            if text:
                parsed_blocks.append({'start_sec': start_sec, 'end_sec': end_sec, 'text': text})
        except: continue
    
    if not parsed_blocks: return ""
    parsed_blocks.sort(key=lambda b: b['start_sec'])
    final_srt = []
    for i, block in enumerate(parsed_blocks, 1):
        final_srt.append(f"{i}\n{to_srt_time(block['start_sec'])} --> {to_srt_time(block['end_sec'])}\n{block['text']}")
    return '\n\n'.join(final_srt)


def display_online_player(video_url, srt_url):
    player_html = f"""
    <video width="100%" controls crossorigin="anonymous">
        <source src="{video_url}" type="video/mp4">
        <track label="کوردی" kind="subtitles" srclang="ku" src="{srt_url}" default>
        Your browser does not support the video tag.
    </video>
    """
    st.header("🎬 پلەیەرى ئۆنلاین")
    st.components.v1.html(player_html, height=450)

# --- Main Processing Logic ---
def process_video(video_input, is_url=False):
    # فۆڵدەری کاتی لەسەر سێرڤەر بەکاردەهێنێت نەک کۆمپیوتەری تۆ
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "source_video.mp4")
        with st.status("📥 ئامادەکردنی ڤیدیۆ لەسەر سێرڤەر...", expanded=True) as status:
            if is_url:
                status.write("داگرتنی ڤیدیۆ لە لینک...")
                # بەکارهێنانی yt-dlp لەسەر سێرڤەر
                subprocess.run(f'yt-dlp -o "{video_path}" -f "best[ext=mp4]" "{video_input}"', shell=True, check=True, capture_output=True, text=True)
            else:
                status.write("پاشەکەوتکردنی ڤیدیۆی ئەپڵۆدکراو...")
                with open(video_path, "wb") as f: f.write(video_input.getbuffer())
            
            if not os.path.exists(video_path):
                st.error("پرۆسەکە وەستا چونکە ڤیدیۆکە بەردەست نییە.")
                return
            status.update(label="✅ ڤیدیۆ ئامادەیە", state="complete")
        
        #... (هەمان لۆژیکی پڕۆسێسکردن وەک وەڵامی پێشوو)
        full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
        subprocess.run(f'ffmpeg -i "{video_path}" -vn -acodec libmp3lame -q:a 2 "{full_audio_path}" -y', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        audio_chunks = split_audio_intelligently(full_audio_path)
        if not audio_chunks: return

        final_srt_content = []
        time_offset = 0.0
        progress_bar = st.progress(0, text="...پڕۆسێسکردنی پارچە دەنگییەکان")
        
        for i, chunk in enumerate(audio_chunks):
            chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp3")
            chunk.export(chunk_path, format="mp3")
            audio_file = genai.upload_file(path=chunk_path)
            while audio_file.state.name == "PROCESSING": time.sleep(2)
            
            raw_srt_chunk = generate_srt_with_retry(audio_file.name)
            if raw_srt_chunk:
                corrected_srt = master_srt_repair_system(raw_srt_chunk)
                offset_srt = offset_srt_timestamps(corrected_srt, time_offset)
                final_srt_content.append(offset_srt)
            
            time_offset += chunk.duration_seconds
            try: genai.delete_file(audio_file.name)
            except Exception: pass
            os.remove(chunk_path)
            progress_bar.progress((i + 1) / len(audio_chunks), text=f"پارچەی {i+1}/{len(audio_chunks)} پڕۆسێس کرا")
        
        full_srt_text = "\n\n".join(final_srt_content)
        final_srt_text = master_srt_repair_system(full_srt_text) 
        srt_path = os.path.join(temp_dir, "final_subtitle.srt")
        with open(srt_path, "w", encoding="utf-8-sig") as f:
            f.write(final_srt_text)

        video_gofile_data = upload_to_gofile(video_path)
        srt_gofile_data = upload_to_gofile(srt_path)
        
        if video_gofile_data and srt_gofile_data:
            st.session_state.processing_done = True
            st.session_state.video_link = video_gofile_data['directLink']
            st.session_state.srt_link = srt_gofile_data['directLink']
            st.session_state.video_page = video_gofile_data['downloadPage']
            st.session_state.srt_page = srt_gofile_data['downloadPage']
            st.rerun()

# --- UI Section ---
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False

if st.session_state.processing_done:
    st.balloons()
    st.header("🎉 کارەکە بە سەرکەوتوویی تەواو بوو!")
    st.success(f"🔗 **لینکی داگرتنی ڤیدیۆ:** {st.session_state.video_page}")
    st.success(f"🔗 **لینکی داگرتنی ژێرنووس:** {st.session_state.srt_page}")
    display_online_player(st.session_state.video_link, st.session_state.srt_link)
    if st.button("پڕۆژەیەکی نوێ"):
        st.session_state.processing_done = False
        st.rerun()
else:
    uploaded_file = st.file_uploader("یەک ڤیدیۆ لێرە هەڵبژێرە:", type=["mp4", "mkv", "mov"])
    st.write("--- یان ---")
    video_url = st.text_input("لینکی ڤیدیۆکە لێرە دابنێ (بۆ نموونە YouTube):")
    if st.button("دروستکردنی ژێرنووس 🚀", key="start_processing"):
        with st.spinner('...تکایە چاوەڕوان بە، ئەم کارە لەوانەیە چەند خولەکێک بخایەنێت'):
            if uploaded_file:
                process_video(uploaded_file, is_url=False)
            elif video_url:
                process_video(video_url, is_url=True)
            else:
                st.warning("تکایە فایلێک ئەپڵۆد بکە یان لینکێک دابنێ.")
