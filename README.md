# � जैन धर्मग्रंथ एवं प्रवचन AI

A Streamlit app that provides accurate Hindi and Prakrit transcriptions of Jain texts and lectures using Google's Gemini AI.

Transcribe **PDF documents** (like Kailash Yatra) and **MP3 audio files** (lectures) with high accuracy while preserving authentic Jain Prakrit spellings and Sanskrit terminology.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

## Features

- 📄 **PDF Transcription**: Extract and translate text from Jain scriptures
- 🎙️ **Audio Transcription**: Convert MP3 lectures to accurate transcripts with timestamps
- 🇮🇳 **Language Support**: Hindi and Prakrit with proper Jain terminology
- ⚡ **Powered by LLM**: Uses the latest multi model for accurate results
- 💾 **Download Results**: Export transcriptions as `.txt` files

## Quick Start

### Run Locally

1. Clone the repository and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the Streamlit app:

   ```bash
   streamlit run streamlit_app.py
   ```

3. Open your browser and go to `http://localhost:8501`

4. In the sidebar, paste your **API Key** (get it [here](https://aistudio.google.com/))

5. Upload a PDF or MP3 file and click **प्रोसेस शुरू करें** to start transcription

### Deploy on Streamlit Community Cloud

1. Push your code to GitHub (ensure `streamlit_app.py` and `requirements.txt` are in the root)

2. Go to [Streamlit Community Cloud](https://share.streamlit.io) and click **New app**

3. Connect your GitHub repository

4. In the **Advanced settings**, add your Gemini API key as a secret:
   - Key: `GEMINI_API_KEY`
   - Value: Your API key from [Google AI Studio](https://aistudio.google.com/)

5. Deploy! Your app will be live with a public URL

## Requirements

- Python 3.9+
- Google Gemini API key ([free tier available](https://aistudio.google.com/))
- Supported file types: PDF, MP3

## Tech Stack

- **Streamlit** - Web framework
- **Google Gemini 2.5 Flash** - AI transcription & translation
- **google-genai** / **google-generativeai** - API client libraries
