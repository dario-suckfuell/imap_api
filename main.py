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
def move(message_uid: str = Query(..., description="IMAP UID of the message")):
    EMAIL = os.environ["IMAP_EMAIL"]
    PASSWORD = os.environ["IMAP_PASSWORD"]
    HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")

    if not message_uid.isdigit():
        return {"status": "invalid_uid", "message_uid": message_uid}

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(HOST)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        # Copy using UID
        status, response = mail.uid('COPY', message_uid, "INBOX.Rechnungen")
        if status != "OK":
            return {
                "status": "copy_failed",
                "imap_response": response
            }

        # Mark the original message for deletion
        status, response = mail.uid('STORE', message_uid, '+FLAGS', '(\Deleted)')
        if status != "OK":
            return {
                "status": "delete_failed",
                "imap_response": response
            }

        # Finalize the deletion
        mail.expunge()

        return {"status": "moved_and_deleted", "message_uid": message_uid}
    
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    
    finally:
        if mail:
            try:
                mail.logout()
            except:
                pass
