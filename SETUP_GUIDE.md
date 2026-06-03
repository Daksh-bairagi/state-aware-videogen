# Setup Guide

## 1. Install Python

Use **Python 3.13+**.

## 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not used, install from `pyproject.toml` with your preferred tool.

## 4. Add API key

Copy `.env.example` to `.env` and add your API key:

```env
GEMINI_API_KEY=your_key_here
```

## 5. Run the app

Main UI:

```bash
streamlit run app.py
```

If Streamlit shows old code, use the alternate file:

```bash
streamlit run ap.py
```
