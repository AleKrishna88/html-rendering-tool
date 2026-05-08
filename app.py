from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "pages.db"
DEFAULT_HEIGHT = 900


def ensure_storage() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                page_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_upload(file_name: str, content: bytes) -> str:
    page_id = uuid.uuid4().hex
    target_path = UPLOADS_DIR / f"{page_id}.html"
    target_path.write_bytes(content)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO pages (page_id, filename, file_path, uploaded_at)
            VALUES (?, ?, ?, ?)
            """,
            (page_id, file_name, str(target_path), uploaded_at),
        )
        conn.commit()

    return page_id


def get_page(page_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT page_id, filename, file_path, uploaded_at FROM pages WHERE page_id = ?",
            (page_id,),
        ).fetchone()


def read_page_html(page: sqlite3.Row) -> str:
    return Path(page["file_path"]).read_text(encoding="utf-8")


def build_share_url(page_id: str) -> str:
    configured_base = os.getenv("PUBLIC_BASE_URL", "").strip()
    if configured_base:
        return f"{configured_base.rstrip('/')}?{urlencode({'page': page_id})}"

    return f"http://localhost:8501?{urlencode({'page': page_id})}"


def render_uploaded_page(page_id: str) -> None:
    page = get_page(page_id)
    if page is None:
        st.error("Pagina non trovata.")
        st.stop()

    html = read_page_html(page)
    st.title(page["filename"])
    st.caption("URL dedicato attivo senza scadenza.")

    uploaded_at = datetime.fromisoformat(page["uploaded_at"]).astimezone()
    st.info(f"Caricato il {uploaded_at:%d/%m/%Y alle %H:%M}.")

    components.html(html, height=DEFAULT_HEIGHT, scrolling=True)


def render_uploader() -> None:
    st.title("HTML Rendering Tool")
    st.write(
        "Carica un file HTML per salvarlo e ottenere un URL dedicato da condividere."
    )

    st.sidebar.header("Configurazione")
    st.sidebar.write(
        "Imposta la variabile d'ambiente `PUBLIC_BASE_URL` se vuoi generare link "
        "pubblici stabili dietro un dominio o un tunnel."
    )

    uploaded_file = st.file_uploader("Seleziona un file HTML", type=["html", "htm"])
    if uploaded_file is None:
        st.caption("I file caricati vengono conservati senza scadenza automatica.")
        return

    raw_content = uploaded_file.getvalue()
    if not raw_content.strip():
        st.error("Il file caricato e' vuoto.")
        return

    try:
        raw_content.decode("utf-8")
    except UnicodeDecodeError:
        st.error("Il file deve essere codificato in UTF-8.")
        return

    page_id = save_upload(uploaded_file.name, raw_content)
    share_url = build_share_url(page_id)

    st.success("Upload completato.")
    st.text_input("URL dedicato", value=share_url, help="Condividi questo link.")

    st.markdown(f"[Apri la pagina renderizzata]({share_url})")

    preview_html = raw_content.decode("utf-8")
    st.subheader("Anteprima")
    components.html(preview_html, height=DEFAULT_HEIGHT, scrolling=True)


def main() -> None:
    st.set_page_config(page_title="HTML Rendering Tool", layout="wide")
    ensure_storage()
    page_id = st.query_params.get("page")
    if page_id:
        render_uploaded_page(str(page_id))
        return

    render_uploader()


if __name__ == "__main__":
    main()
