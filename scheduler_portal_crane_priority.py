from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os

def add_to_calendar(summary, description, start_dt, end_dt):
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/New_York'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/New_York'},
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return f"📅 Event created: {event.get('htmlLink')}"

# Run the test
if __name__ == "__main__":
    start = datetime.now() + timedelta(minutes=5)
    end = start + timedelta(minutes=30)
    print(add_to_calendar(
        summary="Test Job from ECM Scheduler",
        description="This is a test event created to verify OAuth flow.",
        start_dt=start,
        end_dt=end
    ))
