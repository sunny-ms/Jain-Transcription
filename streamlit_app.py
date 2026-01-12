import streamlit as st
import time

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

# --- UI Setup ---
st.set_page_config(page_title="Jain Pathshala AI", page_icon="🙏", layout="wide")

st.title("🙏 Digamber जैन धर्मग्रंथ एवं प्रवचन AI")
st.markdown("इस ऐप के माध्यम से आप **PDF (कैलाश यात्रा आदि)** और **MP3 (प्रवचन)** का सटीक शुद्ध हिंदी एवं प्राकृत अनुवाद कर सकते हैं।")

# Sidebar for Configuration
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("API Key दर्ज करें", type="password")
    st.info("Contact admin for API Key")
    #st.info("API Key [Google AI Studio](https://aistudio.google.com/) से प्राप्त करें।")

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

        # File Uploader
        uploaded_file = st.file_uploader("अपनी फाइल अपलोड करें (PDF या MP3)", type=['pdf', 'mp3'])

        if uploaded_file:
            file_type = "PDF" if uploaded_file.name.endswith(".pdf") else "Audio"
            st.success(f"{file_type} फाइल तैयार है: {uploaded_file.name}")

            if st.button(f"प्रोसेस शुरू करें ({file_type})"):
                try:
                    with st.spinner('App फाइल को प्रोसेस कर रहा है... इसमें 1-2 मिनट लग सकते हैं।'):
                        # 1. MIME Type determine
                        m_type = "application/pdf" if file_type == "PDF" else "audio/mpeg"

                        # 2. Upload to Google GenAI
                        sample_file = client.files.upload(file=uploaded_file, config={'mime_type': m_type})

                        # 3. Wait for ACTIVE state (with timeout)
                        progress_bar = st.progress(0)
                        timeout = 120  # seconds
                        elapsed = 0
                        interval = 2
                        while elapsed < timeout:
                            f_info = client.files.get(name=sample_file.name)
                            # state could be object or string depending on client
                            state = getattr(getattr(f_info, 'state', None), 'name', None) or getattr(f_info, 'state', None)
                            if str(state).upper() == 'ACTIVE':
                                progress_bar.progress(100)
                                break
                            time.sleep(interval)
                            elapsed += interval
                            progress_bar.progress(min(99, int((elapsed / timeout) * 100)))

                        # 4. Select appropriate prompt based on file type
                        if file_type == "Audio":
                            prompt = """Role: You are an expert Jain Literature Archivist and Professional Transcriber.

Task: Listen to the attached audio and provide a verbatim (word-for-word) Hindi transcription with specific attention to Jain terminology.

Instructions:
1. Mantra Accuracy: Follow standard Jain Prakrit spellings for all mantras. For example, use 'णमो अरिहंताणं' instead of 'नमो अरिहंतों', and 'णमो लोए सव्व साहूणं'. 
2. Terminology: Ensure correct spelling for words like 'विषापहार', 'अतिशय', 'जिन शासन', 'तीर्थंकर', 'समवशरण', 'अरिहंत', 'सिद्ध', 'आचार्य', 'उपाध्याय', and 'साधु'.
3. Purity of Language: Preserve the original mix of Sanskrit, Prakrit, and Hindi. Do not translate; only transcribe.

Expected Output: A clean, well-structured document in Unicode Hindi (Devanagari)."""
                        else:  # PDF
                            prompt = """Role: You are an expert Hindi archivist.

Task: Transcribe every word from the attached PDF with 100% accuracy.

Instructions:
1. Capture exact Devanagari characters including honorifics like 'ब्र०'.
2. Do not summarize; provide a verbatim transcription.
3. Maintain page structure by labeling each page clearly.
4. Preserve special symbols like 'ॐ' and '卐'."""

                        # 5. Generate Response
                        response = client.models.generate_content(
                            model='models/gemini-2.5-flash',
                            contents=[f_info, prompt],
                            config={'temperature': 0.1}
                        )

                        # 6. Extract text safely
                        text = None
                        if hasattr(response, 'text'):
                            text = response.text
                        elif hasattr(response, 'candidates'):
                            try:
                                text = response.candidates[0].content
                            except Exception:
                                text = str(response)
                        else:
                            text = str(response)

                        # 7. Display Results
                        st.subheader("निकाल गया टेक्स्ट (Result):")
                        st.text_area("Final Transcript->", text, height=500)

                        # Download Button
                        st.download_button(
                            label="Result डाउनलोड करें (.txt)",
                            data=text,
                            file_name=f"Jain_Output_{int(time.time())}.txt",
                            mime="text/plain"
                        )

                except Exception as e:
                    st.error(f"त्रुटि हुई: {e}")
else:
    st.warning("ऐप चलाने के लिए कृपया साइडबार में API Key डालें।")