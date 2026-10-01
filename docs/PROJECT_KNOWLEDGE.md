# SMS Imported Project Knowledge

## Purpose

This project is a Flask support dashboard for Nimbus services. It connects service queues to Google Sheets, Google Drive recordings, Fireberry CRM, and Inforu-related SMS/DID workflows.

## Main Runtime

- App entry: `app.py`
- Templates and frontend scripts: `template/`
- Static service nav: `template/nav.css` and `template/nav.js`
- Local start helper: `start_app.ps1`
- Python dependencies: `requirements.txt`
- GitHub repository: `https://github.com/QAEngin/sms_imported.git`

## Authentication

The app uses a shared login in `app.py`.

- Allowed users are defined in `ALLOWED_USERS`.
- Shared password is defined in `SHARED_PASSWORD`.
- Most routes redirect to `/login` when `session["logged_in"]` is missing.

## External Systems

- Google Sheets is accessed through `gspread`.
- Google Drive recordings use `google-api-python-client`.
- Fireberry CRM calls use `FIREBERRY_TOKENID` and `CRM_URL` from `.env`.
- SMS configuration uses `SMS_URL` and `SMS_TOKEN` from `.env`.
- Google credentials default to `credentials.json` unless `GOOGLE_APPLICATION_CREDENTIALS` is set.

## Service Pages

- SMS: `/sms`, template `template/index.html`, script `template/script.js`, sheet `SMS`.
- Bot: `/bot`, template `template/bot.html`, script `template/bot.js`, sheet `שירות מענה - בוט`.
- F2M: `/f2m`, template `template/f2m.html`, script `template/f2m.js`, sheet `m2f / f2m`.
- Recordings: `/record`, template `template/record.html`, Google Drive folder from `DRIVE_FOLDER_ID`.
- Recording storage: `/recording-storage`, template `template/recording_storage.html`, script `template/recording_storage.js`, sheet `איחסון הקלטות`.
- Human service: `/human-service`, template `template/human_service.html`, script `template/human_service.js`, sheet `שירות מענה - אנושי`.

## Queue Done Rules

- SMS done updates the SMS sheet and CGR number pool.
- Bot done marks column P checkbox.
- F2M done updates status column H to `בוצע`.
- Recording storage done updates status column H to `בוצע`.
- Human service done marks column N checkbox. The page also filters out rows where column N is checked.
- Recordings done moves the WAV file from the Drive source folder to a `Done` folder.

## Important UI Pattern

Queue pages should show this empty state when there are no waiting customers:

`אין לקוחות בהמתנה`

The side navigation is shared and should stay visually consistent across all pages. Recordings uses the same nav direction and empty-state behavior as the queue pages.

## ToDoFeatures Memory

- Persistent memory for postponed user-management and scoped-access work: `docs/ToDoFeatures.md`
- Draft Supabase schema for that work: `docs/supabase_todo_features_users.sql`

