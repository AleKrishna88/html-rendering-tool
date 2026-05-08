from __future__ import annotations

import mimetypes
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import boto3
import streamlit as st
import streamlit.components.v1 as components
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError


APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "pages.db"
DEFAULT_HEIGHT = 900
DEFAULT_LOCAL_URL = "http://localhost:8501"


@dataclass
class StoredPage:
    page_id: str
    filename: str
    uploaded_at: str
    html: str


class StorageBackend:
    def save_page(self, file_name: str, content: bytes) -> str:
        raise NotImplementedError

    def get_page(self, page_id: str) -> StoredPage | None:
        raise NotImplementedError

    @property
    def mode_label(self) -> str:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, db_path: Path, uploads_dir: Path) -> None:
        self.db_path = db_path
        self.uploads_dir = uploads_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
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

    def save_page(self, file_name: str, content: bytes) -> str:
        page_id = uuid.uuid4().hex
        target_path = self.uploads_dir / f"{page_id}.html"
        target_path.write_bytes(content)

        uploaded_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pages (page_id, filename, file_path, uploaded_at)
                VALUES (?, ?, ?, ?)
                """,
                (page_id, file_name, str(target_path), uploaded_at),
            )
            conn.commit()

        return page_id

    def get_page(self, page_id: str) -> StoredPage | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT page_id, filename, file_path, uploaded_at FROM pages WHERE page_id = ?",
                (page_id,),
            ).fetchone()

        if row is None:
            return None

        html = Path(row["file_path"]).read_text(encoding="utf-8")
        return StoredPage(
            page_id=row["page_id"],
            filename=row["filename"],
            uploaded_at=row["uploaded_at"],
            html=html,
        )

    @property
    def mode_label(self) -> str:
        return "locale"


class S3Storage(StorageBackend):
    def __init__(self, bucket: str, prefix: str, client: BaseClient) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client

    def _object_key(self, page_id: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{page_id}.html"
        return f"{page_id}.html"

    def save_page(self, file_name: str, content: bytes) -> str:
        page_id = uuid.uuid4().hex
        uploaded_at = datetime.now(timezone.utc).isoformat()
        key = self._object_key(page_id)
        content_type = mimetypes.guess_type(file_name)[0] or "text/html"

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata={
                "filename": file_name,
                "uploaded_at": uploaded_at,
            },
        )
        return page_id

    def get_page(self, page_id: str) -> StoredPage | None:
        key = self._object_key(page_id)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"NoSuchKey", "404"}:
                return None
            raise

        metadata = response.get("Metadata", {})
        html = response["Body"].read().decode("utf-8")
        return StoredPage(
            page_id=page_id,
            filename=metadata.get("filename", f"{page_id}.html"),
            uploaded_at=metadata.get("uploaded_at", ""),
            html=html,
        )

    @property
    def mode_label(self) -> str:
        return "s3"


def get_secret(name: str, default: str = "") -> str:
    if name in st.secrets:
        value = st.secrets[name]
        return str(value).strip()
    return os.getenv(name, default).strip()


def create_s3_client() -> BaseClient:
    endpoint_url = get_secret("S3_ENDPOINT_URL")
    region = get_secret("AWS_DEFAULT_REGION", "eu-west-1")
    access_key = get_secret("AWS_ACCESS_KEY_ID")
    secret_key = get_secret("AWS_SECRET_ACCESS_KEY")

    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=endpoint_url or None,
        region_name=region,
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
        config=Config(signature_version="s3v4"),
    )


def get_storage() -> StorageBackend:
    bucket = get_secret("S3_BUCKET")
    if bucket:
        prefix = get_secret("S3_PREFIX", "html-pages")
        return S3Storage(bucket=bucket, prefix=prefix, client=create_s3_client())

    return LocalStorage(db_path=DB_PATH, uploads_dir=UPLOADS_DIR)


def build_share_url(page_id: str) -> str:
    configured_base = get_secret("PUBLIC_BASE_URL")
    if configured_base:
        return f"{configured_base.rstrip('/')}?{urlencode({'page': page_id})}"
    return f"{DEFAULT_LOCAL_URL}?{urlencode({'page': page_id})}"


def format_uploaded_at(uploaded_at: str) -> str:
    if not uploaded_at:
        return "Data di caricamento non disponibile."

    try:
        parsed = datetime.fromisoformat(uploaded_at).astimezone()
    except ValueError:
        return f"Caricato: {uploaded_at}"

    return f"Caricato il {parsed:%d/%m/%Y alle %H:%M}."


def render_uploaded_page(storage: StorageBackend, page_id: str) -> None:
    page = storage.get_page(page_id)
    if page is None:
        st.error("Pagina non trovata.")
        st.stop()

    st.title(page.filename)
    st.caption("URL dedicato attivo senza scadenza applicativa.")
    st.info(format_uploaded_at(page.uploaded_at))
    components.html(page.html, height=DEFAULT_HEIGHT, scrolling=True)


def render_sidebar(storage: StorageBackend) -> None:
    st.sidebar.header("Configurazione")
    st.sidebar.write(
        "Per link pubblici stabili imposta `PUBLIC_BASE_URL` nei secrets di Streamlit."
    )
    st.sidebar.write(f"Storage attivo: `{storage.mode_label}`")

    if storage.mode_label == "s3":
        st.sidebar.success("I file HTML vengono salvati su storage persistente esterno.")
    else:
        st.sidebar.warning(
            "Fallback locale attivo. Su Streamlit Community Cloud non e' adatto a una "
            "persistenza garantita."
        )


def render_uploader(storage: StorageBackend) -> None:
    st.title("HTML Rendering Tool")
    st.write(
        "Carica un file HTML per salvarlo e ottenere un URL dedicato da condividere."
    )
    render_sidebar(storage)

    uploaded_file = st.file_uploader("Seleziona un file HTML", type=["html", "htm"])
    if uploaded_file is None:
        st.caption("Con storage persistente esterno, i file restano disponibili senza TTL.")
        return

    raw_content = uploaded_file.getvalue()
    if not raw_content.strip():
        st.error("Il file caricato e' vuoto.")
        return

    try:
        preview_html = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        st.error("Il file deve essere codificato in UTF-8.")
        return

    page_id = storage.save_page(uploaded_file.name, raw_content)
    share_url = build_share_url(page_id)

    st.success("Upload completato.")
    st.text_input("URL dedicato", value=share_url, help="Condividi questo link.")
    st.markdown(f"[Apri la pagina renderizzata]({share_url})")

    st.subheader("Anteprima")
    components.html(preview_html, height=DEFAULT_HEIGHT, scrolling=True)


def main() -> None:
    st.set_page_config(page_title="HTML Rendering Tool", layout="wide")
    storage = get_storage()
    page_id = st.query_params.get("page")
    if page_id:
        render_sidebar(storage)
        render_uploaded_page(storage, str(page_id))
        return

    render_uploader(storage)


if __name__ == "__main__":
    main()
