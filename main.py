from fastapi import FastAPI, Query
import imaplib
import os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/move")
def move(message_id: str = Query(..., description="Full Message-ID including angle brackets")):
    EMAIL = os.environ["IMAP_EMAIL"]
    PASSWORD = os.environ["IMAP_PASSWORD"]
    HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")

    try:
        mail = imaplib.IMAP4_SSL(HOST)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        # Search for email with exact Message-ID header
        search_criteria = f'(HEADER Message-ID "{message_id}")'
        status, data = mail.search(None, search_criteria)

        if status != "OK" or not data[0]:
            return {"status": "not_found", "message_id": message_id}

        email_ids = data[0].split()
        email_id = email_ids[0]

        mail.create("Rechnungen")  # idempotent: won't fail if exists
        status, _ = mail.copy(email_id, "Rechnungen")
        if status != "OK":
            return {"status": "copy_failed"}

        # Uncomment to delete original after copy:
        # mail.store(email_id, "+FLAGS", "\\Deleted")
        # mail.expunge()

        return {"status": "moved", "message_id": message_id}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        mail.logout()
