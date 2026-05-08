# HTML Rendering Tool

App Streamlit per:

- caricare un file HTML;
- salvarlo su storage persistente;
- generare un URL dedicato del tipo `?page=<id>`;
- visualizzare la pagina renderizzata.

## Come funziona

L'app supporta due modalita':

- `S3` consigliata per Streamlit Community Cloud: salva gli HTML in un bucket persistente.
- `locale` utile solo per sviluppo: salva file e metadati nella cartella `data/`.

Se imposti `S3_BUCKET`, l'app usa automaticamente il backend S3-compatible.

## Avvio locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy su Streamlit Community Cloud

1. Pubblica il progetto su GitHub.
2. Crea una nuova app su Streamlit Community Cloud.
3. Nei secrets dell'app configura almeno:

```toml
PUBLIC_BASE_URL = "https://tuo-subdomain.streamlit.app"
S3_BUCKET = "nome-bucket"
S3_PREFIX = "html-pages"
AWS_DEFAULT_REGION = "eu-west-1"
AWS_ACCESS_KEY_ID = "..."
AWS_SECRET_ACCESS_KEY = "..."
```

4. Se usi uno storage S3-compatible diverso da AWS, aggiungi anche:

```toml
S3_ENDPOINT_URL = "https://<endpoint-provider>"
```

## Note importanti

- Gli URL dedicati restano stabili fintanto che l'oggetto rimane nel bucket.
- Streamlit Community Cloud mantiene l'URL dell'app, ma l'app puo' andare in sleep per inattivita'.
- La persistenza "senza scadenza" dipende dalle policy del tuo bucket: non impostare lifecycle rules di cancellazione se vuoi conservarli indefinitamente.
