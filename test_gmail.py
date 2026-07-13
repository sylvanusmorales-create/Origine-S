from dotenv import load_dotenv
load_dotenv()
from core.gmail import gmail_read
print(gmail_read(max_emails=2, unread_only=False))