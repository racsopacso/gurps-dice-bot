from __future__ import annotations

import os.path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from pydantic import ValidationError

from player_defn import Skill

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "1f-zlmNjaQyq1YiOUCs0Wzjifm2mZp6LKHtFZoooepag"
SKILLS_RANGE = "Skills!A1:G20"



def get_sheet_for_user(spreadsheed_id: str):
  """Shows basic usage of the Sheets API.
  Prints values from a sample spreadsheet.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.

  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  service = build("sheets", "v4", credentials=creds)

  # Call the Sheets API
  sheet = service.spreadsheets()
  try:
    result = (
        sheet.values()
        .get(spreadsheetId=spreadsheed_id, range=SKILLS_RANGE)
        .execute()
    )

  except HttpError:
    return None
  
  values = result.get("values", [])

  valueiter = iter(values)

  header = next(valueiter)

  header = [elem.lower() for elem in header]

  name_idx = header.index("skills")
  roll_idx = header.index("roll")

  try:
    note_idx = header.index("notes")
  except ValueError:
    note_idx = None

  skills: list[Skill] = []

  for value in valueiter:
    if not value:
      continue

    print(value)

    try:
      if note_idx != None and note_idx < len(value):
        note = note if (note := value[note_idx]) else None
      else:
        note = None
      skills.append(Skill(name=value[name_idx], value=value[roll_idx], note=note))
    except ValidationError as e:
      print(f"Validation failed: {e}")
    
  return skills

if __name__ == "__main__":
  foo = get_sheet_for_user("1dROo7t4H54WmJ40q2J-C9YfpX8nztmbal_ztu1XHSCg")
  foo = get_sheet_for_user("1f-zlmNjaQyq1YiOUCs0Wzjifm2mZp6LKHtFZoooepag")
  breakpoint()