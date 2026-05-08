# HTML Rendering Tool

Piccola app Streamlit per:

- caricare un file HTML;
- salvarlo in locale senza scadenza automatica;
- ottenere un URL dedicato del tipo `?page=<id>`;
- visualizzare il rendering della pagina caricata.

## Avvio

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## URL condivisibili

Per generare link pubblici corretti, imposta `PUBLIC_BASE_URL` con l'URL esterno
dell'applicazione:

```bash
export PUBLIC_BASE_URL="https://tuo-dominio-o-tunnel"
streamlit run app.py
```

Se `PUBLIC_BASE_URL` non e' impostata, l'app usa `http://localhost:8501` come base.

## Note

- I file HTML vengono memorizzati in `data/uploads/`.
- I metadati vengono salvati in `data/pages.db`.
- Nessuna scadenza viene applicata ai contenuti salvati.
