import imaplib
import smtplib
import email
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime
from dotenv import load_dotenv

# Charge le fichier .env depuis le dossier parent
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GMAIL = os.environ.get("GMAIL_EMAIL", "")
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Pour déboguer (à supprimer après)
print(f"📧 GMAIL chargé : {GMAIL}")
print(f"🔑 PASSWORD chargé : {'*' * len(PASSWORD) if PASSWORD else 'VIDE'}")


def _decode_header(value: str) -> str:
    parts = decode_header(value)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def gmail_read(max_emails: int = 5, folder: str = "INBOX", unread_only: bool = False) -> str:
    if not GMAIL or not PASSWORD:
        return "⚠️ Erreur : GMAIL_EMAIL ou GMAIL_APP_PASSWORD non configuré dans le fichier .env"
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(GMAIL, PASSWORD)
        mail.select(folder)

        criteria = "UNSEEN" if unread_only else "ALL"
        _, data = mail.search(None, criteria)
        ids = data[0].split()
        if not ids:
            mail.logout()
            return "Aucun email trouvé."

        ids = ids[-max_emails:]
        results = []

        for eid in reversed(ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject = _decode_header(msg.get("Subject", "(sans objet)"))
            sender = _decode_header(msg.get("From", "Inconnu"))
            date = msg.get("Date", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")[:500]
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")[:500]

            results.append(
                f"De : {sender}\n"
                f"Objet : {subject}\n"
                f"Date : {date}\n"
                f"Aperçu : {body.strip()[:300]}"
            )

        mail.logout()
        return "\n\n---\n\n".join(results)

    except Exception as e:
        return f"Erreur Gmail (lecture) : {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    if not GMAIL or not PASSWORD:
        return "⚠️ Erreur : GMAIL_EMAIL ou GMAIL_APP_PASSWORD non configuré dans le fichier .env"
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL, PASSWORD)
            server.sendmail(GMAIL, to, msg.as_string())

        return f"Email envoyé à {to} — Objet : {subject}"

    except Exception as e:
        return f"Erreur Gmail (envoi) : {e}"


def gmail_search(query: str, max_emails: int = 5) -> str:
    if not GMAIL or not PASSWORD:
        return "⚠️ Erreur : GMAIL_EMAIL ou GMAIL_APP_PASSWORD non configuré dans le fichier .env"
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(GMAIL, PASSWORD)
        mail.select("INBOX")

        _, data = mail.search(None, f'SUBJECT "{query}"')
        ids = data[0].split()

        if not ids:
            _, data = mail.search(None, f'BODY "{query}"')
            ids = data[0].split()

        if not ids:
            mail.logout()
            return f"Aucun email trouvé pour : {query}"

        ids = ids[-max_emails:]
        results = []

        for eid in reversed(ids):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode_header(msg.get("Subject", "(sans objet)"))
            sender = _decode_header(msg.get("From", "Inconnu"))
            date = msg.get("Date", "")
            results.append(f"De : {sender}\nObjet : {subject}\nDate : {date}")

        mail.logout()
        return "\n\n---\n\n".join(results)

    except Exception as e:
        return f"Erreur Gmail (recherche) : {e}"