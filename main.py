from fastapi import FastAPI, Query, Header, HTTPException, Depends
import imaplib
import os

API_KEY = os.environ["API_KEY"]

app = FastAPI()

def verify_api_key(authorization: str = Header(...)):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {"status": "running"}

@app.get("/move", dependencies=[Depends(verify_api_key)])
def move(message_id: str = Query(..., description="Full Message-ID including angle brackets")):
    EMAIL = os.environ["IMAP_EMAIL"]
    PASSWORD = os.environ["IMAP_PASSWORD"]
    HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")

    try:
        mail = imaplib.IMAP4_SSL(HOST)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        search_criteria = f'(HEADER Message-ID "{message_id}")'
        status, data = mail.search(None, search_criteria)

        if status != "OK" or not data[0]:
            return {"status": "not_found", "message_id": message_id}

        email_ids = data[0].split()
        email_id = email_ids[0]

        mail.create("Rechnungen")  # idempotent
        status, _ = mail.copy(email_id, "Rechnungen")
        if status != "OK":
            return {"status": "copy_failed"}

        # Optional: mark for deletion
        # mail.store(email_id, "+FLAGS", "\\Deleted")
        # mail.expunge()

        return {"status": "moved", "message_id": message_id}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        mail.logout()
