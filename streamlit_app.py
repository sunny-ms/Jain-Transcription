import streamlit as st
import time
import io
import tempfile
import os
import traceback
from docx import Document
from pypdf import PdfReader, PdfWriter

# Try multiple import paths so the app works with different GenAI client packages
try:
    import genai
except Exception:
    try:
        import google.genai as genai
    except Exception:
        try:
            import google.generativeai as genai
        except Exception:
            genai = None

# --- Prompt Constants ---
AUDIO_PROMPT = """Role: You are an expert Jain Literature Archivist and Professional Transcriber.

Task: Listen to the attached audio and provide a verbatim (word-for-word) Hindi transcription with specific attention to Jain terminology.

Instructions:
1. Mantra Accuracy: Follow standard Jain Prakrit spellings for all mantras. For example, use 'णमो अरिहंताणं' instead of 'नमो अरिहंतों', and 'णमो लोए सव्व साहूणं'.
2. Terminology: Ensure correct spelling for words like 'विषापहार', 'अतिशय', 'जिन शासन', 'तीर्थंकर', 'समवशरण', 'अरिहंत', 'सिद्ध', 'आचार्य', 'उपाध्याय', and 'साधु'.
3. Purity of Language: Preserve the original mix of Sanskrit, Prakrit, and Hindi. Do not translate; only transcribe.

Expected Output: A clean, well-structured document in Unicode Hindi (Devanagari)."""

PDF_PROMPT = """Role: You are an expert Hindi archivist.

Task: Transcribe every word from the attached PDF with 100% accuracy.

Instructions:
1. Capture exact Devanagari characters including honorifics like 'ब्र०'.
2. Do not summarize; provide a verbatim transcription.
3. Maintain page structure by labeling each page clearly.
4. Preserve special symbols like 'ॐ' and '卐'.
5. REPETITION CHECK & PATTERN BREAKING: If you find yourself repeating the same word, phrase, or numbering sequence more than 3 times, STOP. This is a sign of a hallucination loop. Re-scan the page specifically for changes in text. Do not assume a list follows a uniform pattern; verify every single character against the visual source.
6. MULTI-COLUMN LAYOUT HANDLING: If a page contains multiple columns (like an index or bibliography), transcribe them column-by-column or row-by-row in a clear, structured list. Do not read across the columns as if they are a single sentence. If an entry is split by a page break, merge it into a single coherent line in your transcription to maintain context.
7. DENSE DATA FORMATTING: For pages containing dense indices (like 'ग्रन्थाक्रम'), prioritize a Numbered List format. Use the format [Number]. [Title] ([Page/Reference]). If the text becomes too dense to follow in a standard paragraph, force a new line for every new entry to prevent the model's logic from "stacking" words and looping."""


# --- Helper: Split PDF into chunks ---
def split_pdf(pdf_bytes: bytes, chunk_size: int, start_page: int = 0, end_page: int = None) -> list:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    end_page = end_page if end_page is not None else total
    end_page = min(end_page, total)
    chunks = []
    for s in range(start_page, end_page, chunk_size):
        writer = PdfWriter()
        for p in range(s, min(s + chunk_size, end_page)):
            writer.add_page(reader.pages[p])
        buf = io.BytesIO()
        writer.write(buf)
        chunks.append(buf.getvalue())
    return chunks


# --- Helper: Write to error log ---
def log_error(temp_dir: str, chunk_idx: int, error_msg: str, full_trace: str):
    if not temp_dir:
        return
    log_path = os.path.join(temp_dir, "error_log.txt")
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"समय (Time): {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"भाग (Chunk): {chunk_idx + 1}\n")
        f.write(f"त्रुटि (Error): {error_msg}\n")
        f.write(f"Full Traceback:\n{full_trace}\n")


# --- UI Setup ---
st.set_page_config(page_title="Jain Pathshala AI", page_icon="🙏", layout="wide")

st.title("🙏 Digamber जैन धर्मग्रंथ एवं प्रवचन AI")
st.markdown("इस ऐप के माध्यम से आप **PDF (कैलाश यात्रा आदि)** और **MP3 (प्रवचन)** का सटीक शुद्ध हिंदी एवं प्राकृत अनुवाद कर सकते हैं।")

# Sidebar for Configuration
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("API Key दर्ज करें", type="password")
    st.info("Contact admin for API Key")
    st.divider()
    chunk_size = st.number_input(
        "PDF Chunk Size (pages per part)",
        min_value=1, max_value=100, value=15, step=1,
        help="Large PDFs will be split into parts of this many pages"
    )

# --- Logic ---
if api_key:
    if genai is None:
        st.error("Google GenAI क्लाइंट इंस्टॉल नहीं मिला। कृपया चलाएँ: `pip install google-genai` या `pip install google-generativeai` और ऐप को फिर से चालू करें।")
    else:
        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            st.error(f"GenAI क्लाइंट बनाने में त्रुटि: {e}")
            st.stop()

        # --- Session state initialization ---
        for k, v in {
            'processing_active': False,
            'chunk_results': [],
            'chunk_count': 0,
            'chunk_bytes': [],
            'pdf_bytes': b'',
            'audio_bytes': b'',
            'current_chunk_index': 0,
            'processing_error': None,
            'processing_complete': False,
            'session_temp_dir': None,
            'chunk_temp_files': [],
            'is_pdf': False,
        }.items():
            if k not in st.session_state:
                st.session_state[k] = v

        # File Uploader
        uploaded_file = st.file_uploader("अपनी फाइल अपलोड करें (PDF या MP3)", type=['pdf', 'mp3'])

        if uploaded_file:
            file_type = "PDF" if uploaded_file.name.endswith(".pdf") else "Audio"
            st.success(f"{file_type} फाइल तैयार है: {uploaded_file.name}")

            # --- Process button ---
            if st.button(f"प्रोसेस शुरू करें ({file_type})"):
                # Cleanup previous temp files
                for p in st.session_state.get('chunk_temp_files', []):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
                td = st.session_state.get('session_temp_dir')
                if td and os.path.isdir(td):
                    try:
                        os.rmdir(td)
                    except OSError:
                        pass

                st.session_state.update({
                    'processing_active': True,
                    'chunk_results': [],
                    'current_chunk_index': 0,
                    'processing_error': None,
                    'processing_complete': False,
                    'chunk_temp_files': [],
                })

                if file_type == "PDF":
                    pdf_bytes = uploaded_file.read()
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['is_pdf'] = True
                    st.session_state['session_temp_dir'] = tempfile.mkdtemp(prefix='jain_')
                    chunks = split_pdf(pdf_bytes, chunk_size)
                    st.session_state['chunk_bytes'] = chunks
                    st.session_state['chunk_count'] = len(chunks)
                    st.session_state['chunk_results'] = [None] * len(chunks)
                else:
                    st.session_state['audio_bytes'] = uploaded_file.read()
                    st.session_state['is_pdf'] = False
                    st.session_state['chunk_count'] = 1
                    st.session_state['chunk_results'] = [None]

                st.rerun()

        # --- Incremental results display (shown before processing so prior chunks are visible) ---
        done = [r for r in st.session_state.chunk_results if r is not None]
        if done:
            st.subheader("निकाल गया टेक्स्ट (Result):")
            for i, result in enumerate(st.session_state.chunk_results):
                if result is not None:
                    label = f"भाग {i + 1}" if st.session_state.chunk_count > 1 else "परिणाम"
                    with st.expander(label, expanded=(i == len(done) - 1)):
                        st.text_area("", result, height=300,
                                     key=f"chunk_out_{i}", label_visibility="collapsed")

        # --- Error display with resume + partial download options ---
        if st.session_state.processing_error:
            failed_idx = st.session_state.current_chunk_index
            st.error(f"भाग {failed_idx + 1} पर त्रुटि: {st.session_state.processing_error}")

            col_resume, col_skip, col_dl = st.columns(3)

            with col_resume:
                if st.button(f"भाग {failed_idx + 1} से पुनः शुरू करें"):
                    st.session_state['processing_error'] = None
                    st.session_state['processing_active'] = True
                    st.rerun()

            with col_skip:
                if st.button(f"भाग {failed_idx + 1} छोड़ें, आगे बढ़ें"):
                    st.session_state['processing_error'] = None
                    st.session_state['chunk_results'][failed_idx] = "[यह भाग छोड़ा गया (skipped)]"
                    st.session_state['current_chunk_index'] = failed_idx + 1
                    if failed_idx + 1 >= st.session_state.chunk_count:
                        st.session_state['processing_complete'] = True
                    else:
                        st.session_state['processing_active'] = True
                    st.rerun()

            with col_dl:
                # Download what has been processed so far
                partial_results = [r for r in st.session_state.chunk_results if r is not None]
                if partial_results:
                    partial_text = "\n\n---\n\n".join(partial_results)
                    st.download_button(
                        label="📄 अब तक का परिणाम डाउनलोड करें",
                        data=partial_text,
                        file_name=f"Jain_Partial_{int(time.time())}.txt",
                        mime="text/plain"
                    )

            # Error log download
            log_path = os.path.join(st.session_state['session_temp_dir'], "error_log.txt") \
                if st.session_state['session_temp_dir'] else None
            if log_path and os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as lf:
                    log_content = lf.read()
                st.download_button(
                    label="📋 Error Log डाउनलोड करें",
                    data=log_content,
                    file_name=f"Jain_ErrorLog_{int(time.time())}.txt",
                    mime="text/plain"
                )

        # --- Processing loop: one chunk per rerun ---
        if st.session_state.processing_active:
            idx = st.session_state.current_chunk_index
            total = st.session_state.chunk_count

            st.progress(idx / total if total > 0 else 0,
                        text=f"प्रोसेसिंग: {idx}/{total} भाग पूर्ण")

            if idx < total:
                with st.status(f"भाग {idx + 1}/{total} प्रोसेस हो रहा है...", expanded=True):
                    try:
                        if st.session_state.is_pdf:
                            upload_source = io.BytesIO(st.session_state['chunk_bytes'][idx])
                            m_type = "application/pdf"
                            prompt = PDF_PROMPT + f"\n8. CHUNK INFO: This is part {idx + 1} of {total}. Transcribe all content in this chunk."
                        else:
                            upload_source = io.BytesIO(st.session_state['audio_bytes'])
                            m_type = "audio/mpeg"
                            prompt = AUDIO_PROMPT

                        st.write("Gemini पर अपलोड हो रहा है...")
                        sample_file = client.files.upload(file=upload_source, config={'mime_type': m_type})

                        # Poll for ACTIVE state (120s timeout)
                        st.write("फाइल तैयार होने का इंतज़ार...")
                        elapsed = 0
                        while elapsed < 120:
                            f_info = client.files.get(name=sample_file.name)
                            state = getattr(getattr(f_info, 'state', None), 'name', None) or getattr(f_info, 'state', None)
                            if str(state).upper() == 'ACTIVE':
                                break
                            time.sleep(2)
                            elapsed += 2

                        st.write("Gemini से उत्तर प्राप्त हो रहा है...")
                        max_retries = 3
                        last_err = None
                        last_trace = None
                        response = None
                        for attempt in range(1, max_retries + 1):
                            try:
                                response = client.models.generate_content(
                                    model='models/gemini-2.5-flash',
                                    contents=[f_info, prompt],
                                    config={'temperature': 0.1}
                                )
                                break
                            except Exception as gen_err:
                                last_err = gen_err
                                last_trace = traceback.format_exc()
                                if attempt < max_retries:
                                    wait = attempt * 30  # 30s, 60s — gives 503 time to recover
                                    st.write(f"प्रयास {attempt} विफल ({gen_err}), {wait}s बाद पुनः प्रयास...")
                                    time.sleep(wait)
                        if response is None:
                            raise Exception(f"3 प्रयासों के बाद भी विफल: {last_err}")

                        # Extract text safely
                        if hasattr(response, 'text'):
                            text = response.text
                        elif hasattr(response, 'candidates'):
                            try:
                                text = response.candidates[0].content
                            except Exception:
                                text = str(response)
                        else:
                            text = str(response)

                        # Save to temp file
                        if st.session_state['session_temp_dir']:
                            temp_path = os.path.join(
                                st.session_state['session_temp_dir'],
                                f"chunk_{idx:03d}.txt"
                            )
                            with open(temp_path, 'w', encoding='utf-8') as tf:
                                tf.write(text)
                            st.session_state['chunk_temp_files'].append(temp_path)

                        st.session_state['chunk_results'][idx] = text
                        st.session_state['current_chunk_index'] = idx + 1

                        # Clean up Gemini file immediately after use
                        try:
                            client.files.delete(name=sample_file.name)
                        except Exception:
                            pass

                    except Exception as e:
                        full_trace = traceback.format_exc()
                        log_error(st.session_state['session_temp_dir'], idx, str(e), full_trace)
                        st.session_state['processing_error'] = str(e)
                        st.session_state['processing_active'] = False
                        st.rerun()

                if st.session_state['current_chunk_index'] >= total:
                    st.session_state['processing_active'] = False
                    st.session_state['processing_complete'] = True

                st.rerun()  # immediately process next chunk

        # --- Final combined download (only when all chunks done) ---
        if st.session_state.processing_complete:
            full_text = "\n\n---\n\n".join(
                r for r in st.session_state.chunk_results if r is not None
            )

            if st.session_state.chunk_count > 1:
                st.subheader("पूर्ण परिणाम (Complete Result):")
                st.text_area("Final Transcript->", full_text, height=500)

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📄 Text (.txt) डाउनलोड करें",
                    data=full_text,
                    file_name=f"Jain_Output_{int(time.time())}.txt",
                    mime="text/plain"
                )
            with col2:
                doc = Document()
                for r in st.session_state.chunk_results:
                    if r:
                        doc.add_paragraph(r)
                        doc.add_paragraph()
                docx_buffer = io.BytesIO()
                doc.save(docx_buffer)
                docx_buffer.seek(0)
                st.download_button(
                    label="📋 Word (.docx) डाउनलोड करें",
                    data=docx_buffer.getvalue(),
                    file_name=f"Jain_Output_{int(time.time())}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

else:
    st.warning("ऐप चलाने के लिए कृपया साइडबार में API Key डालें।")
