# AI Resume & Application Assistant

Streamlit app for AI resume creation, ATS analysis, job matching, cover letters, application messages and interview preparation.

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optional local secret: create `.streamlit/secrets.toml`:

```toml
GOOGLE_API_KEY = "your_gemini_api_key_here"
```

To enable **Continue with Google**, create a Google OAuth Web application in
Google Cloud Console and add these values to the same secrets file. Add
`http://localhost:8501/` as an authorized redirect URI:

```toml
GOOGLE_CLIENT_ID = "your-google-client-id"
GOOGLE_CLIENT_SECRET = "your-google-client-secret"
GOOGLE_REDIRECT_URI = "http://localhost:8501/"
```

Email/password sign-up and login work locally for the current Streamlit
session. A production deployment should replace the session store with a
database and server-side authentication provider.

Never commit that file.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository and upload all files.
2. Open https://share.streamlit.io/
3. Sign in with GitHub and choose **Create app**.
4. Select the repository, `main` branch, and `app.py` as the entrypoint.
5. In **Advanced settings → Secrets**, add:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

6. Click **Deploy**.

The app will get a `streamlit.app` URL.

## Notes

- The app works in fallback mode without an API key, using local keyword analysis and templates.
- AI features use the Google Gemini API with the `google-genai` SDK. The app accepts `GOOGLE_API_KEY` or `GEMINI_API_KEY`.
- Do not put API keys in Python source code or GitHub.
