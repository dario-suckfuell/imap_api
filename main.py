from fastapi import FastAPI, Query, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from email import message_from_bytes
from email.policy import default as default_policy
import io
import zipfile

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

@app.get("/attachments", dependencies=[Depends(verify_api_key)])
def download_attachments(
    message_uid: str = Query(..., description="IMAP UID of the message to fetch PDF attachments from")
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

        status, data = mail.uid('fetch', message_uid, '(RFC822)')
        if status != "OK" or not data or data[0] is None:
            return {"status": "fetch_failed", "imap_response": data}

        raw_email = data[0][1]
        email_message = message_from_bytes(raw_email, policy=default_policy)

        pdf_found = False
        zip_buffer = io.BytesIO()
        counter = 1

        def gather_pdfs(msg):
            nonlocal pdf_found, counter
            for part in msg.iter_parts():
                maintype = part.get_content_maintype()

                if maintype == "multipart":
                    gather_pdfs(part)
                    continue

                if part.get_content_type() == "application/pdf":
                    filename = part.get_filename() or f"attachment_{counter}.pdf"
                    counter += 1
                    payload = part.get_payload(decode=True)
                    if payload is not None:
                        zip_file.writestr(filename, payload)
                        pdf_found = True
                elif part.get_content_type() == "message/rfc822":
                    nested_bytes = part.get_payload(decode=True)
                    if nested_bytes:
                        nested_msg = message_from_bytes(nested_bytes, policy=default_policy)
                        gather_pdfs(nested_msg)

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            gather_pdfs(email_message)

        if not pdf_found:
            return {"status": "no_attachments", "message_uid": message_uid}

        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=pdf_attachments_{message_uid}.zip"
            }
        )

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
