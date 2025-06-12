from fastapi import FastAPI, Query, Header, HTTPException, Depends
import imaplib
import os

# Retrieve API key lazily to avoid import-time crashes when the variable
# is not set. Applications without the required environment variable would
# previously fail to start with a KeyError.
API_KEY = os.getenv("API_KEY")

app = FastAPI()

def verify_api_key(authorization: str = Header(...)):
    expected_key = API_KEY or os.getenv("API_KEY")
    if expected_key is None:
        raise HTTPException(status_code=500, detail="API key not configured")
    if authorization != f"Bearer {expected_key}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {"status": "running"}

@app.get("/move", dependencies=[Depends(verify_api_key)])
def move(
    message_uid: str = Query(..., description="IMAP UID of the message"),
    target_folder: str = Query(..., description="Target folder to move the message to")
):
    EMAIL = os.environ["IMAP_EMAIL"]
    PASSWORD = os.environ["IMAP_PASSWORD"]
    HOST = os.environ.get("IMAP_HOST")

    if not message_uid.isdigit():
        return {"status": "invalid_uid", "message_uid": message_uid}

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(HOST)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        status, response = mail.uid('COPY', message_uid, target_folder)
        if status != "OK":
            return {
                "status": "copy_failed",
                "imap_response": response
            }

        status, response = mail.uid('STORE', message_uid, '+FLAGS', '(\Deleted)')
        if status != "OK":
            return {
                "status": "delete_failed",
                "imap_response": response
            }

        mail.expunge()

        return {
            "status": "moved_and_deleted",
            "message_uid": message_uid,
            "target_folder": target_folder
        }

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        if mail:
            try:
                mail.logout()
            except:
                pass


@app.get("/label", dependencies=[Depends(verify_api_key)])
def label(
    message_uid: str = Query(..., description="IMAP UID of the message to label"),
    target_label: str = Query(..., description="IMAP label to assign to the message")
):
    EMAIL = os.environ["IMAP_EMAIL"]
    PASSWORD = os.environ["IMAP_PASSWORD"]
    HOST = os.environ.get("IMAP_HOST")

    if not message_uid.isdigit():
        return {"status": "invalid_uid", "message_uid": message_uid}

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(HOST)
        mail.login(EMAIL, PASSWORD)
        mail.select("INBOX")

        status, response = mail.uid('STORE', message_uid, '+FLAGS', f'({target_label})')
        if status != "OK":
            return {
                "status": "label_failed",
                "imap_response": response
            }

        return {
            "status": "labeled",
            "label": target_label,
            "message_uid": message_uid
        }

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        if mail:
            try:
                mail.logout()
            except:
                pass

