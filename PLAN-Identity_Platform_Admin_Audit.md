# תכנית מימוש: מעבר ל־Identity Platform + Admin/Audit עבור `sms_manager`

## Summary
האפליקציה הקיימת היא Flask מונוליתית עם `app.py` יחיד, `session` מבוסס cookie, ו־login ידני דרך `ALLOWED_USERS` + `SHARED_PASSWORD`.  
ב־v1 נעבור ל־Identity Platform עם `email/password`, נגביל גישה ל־`@nimbusip.com`, נוסיף `custom claims` עבור `admin` / `user`, ונבנה שני מסכי אדמין חדשים: `Users` ו־`Audit Log`.

ברירת המחדל שננעלה לתכנית:
- חוויית התחברות: `Email + Password`
- אדמין ראשון: `admin@nimbusip.com`
- Audit v1: `admin actions + auth events`

## Task List

### 1. מיפוי והקשחת בסיס האבטחה
- להוציא מהקוד את `ALLOWED_USERS`, `SHARED_PASSWORD`, ו־fallback חלש ל־`SECRET_KEY`.
- להגדיר קונפיגורציה מסודרת ל־auth דרך env vars בלבד:
  - `IDENTITY_PLATFORM_PROJECT_ID`
  - `IDENTITY_PLATFORM_WEB_API_KEY`
  - `IDENTITY_PLATFORM_AUTH_DOMAIN` אם יידרש
  - `FIREBASE_ADMIN_CREDENTIALS` או שימוש ב־ADC של Cloud Run
  - `ALLOWED_EMAIL_DOMAIN=nimbusip.com`
  - `SESSION_COOKIE_SECURE=true` בסביבת Cloud Run
- להוסיף שכבת config אחת מרכזית במקום קריאות `os.environ.get(...)` מפוזרות.
- להחליף deploy של Cloud Run מ־`--allow-unauthenticated` למודל שבו האפליקציה עדיין נגישה ציבורית ברמת HTTP, אבל כל מסך עסקי מוגן ב־auth אפליקטיבי; לא להשתמש ב־default service account.

### 2. הקמת Identity Platform בצד GCP
- להפעיל Identity Platform בפרויקט GCP של האפליקציה.
- להפעיל provider של `Email/Password`.
- להגדיר Service Account ייעודי ל־Cloud Run עם ההרשאות המינימליות:
  - ניהול משתמשים דרך Admin SDK
  - קריאת Cloud Logging עבור audit
  - גישה ל־Secret Manager לסודות
- להעביר סודות ל־Secret Manager:
  - מפתחות service account אם לא משתמשים ב־ADC
  - `SECRET_KEY`
  - כל טוקנים קיימים של המערכת
- לעדכן `cloudbuild.yaml`/תהליך deployment כך ש־Cloud Run רץ עם ה־service account הייעודי ועם משתני הסביבה החדשים.

### 3. חסימת דומיינים שאינם `@nimbusip.com`
- שכבת הגנה 1 באפליקציה:
  - במסך login וב־backend לאפשר רק אימיילים שמסתיימים ב־`@nimbusip.com`.
  - להחזיר הודעת שגיאה אחידה ולא לחשוף האם המשתמש קיים.
- שכבת הגנה 2 ב־Identity Platform:
  - להוסיף blocking function של `beforeCreate` וגם `beforeSignIn` על Cloud Run/Functions.
  - החסימה תבדוק domain ותדחה כל אימייל שאינו `nimbusip.com`.
- להגדיר לוג ברור עבור דחיות domain כדי שיופיע ב־Audit.

### 4. שכבת Auth חדשה בתוך Flask
- להחליף את `/login` הקיים בזרימה חדשה:
  - `GET /login` מציג form
  - `POST /auth/login` מקבל email/password
  - השרת מבצע sign-in מול Identity Platform REST API
  - השרת מאמת ID token, טוען claims, ויוצר session אפליקטיבי חדש
- להוסיף `auth service` נפרד מתוך `app.py` כדי לא לרכז שוב את כל הלוגיקה בקובץ אחד.
- להגדיר decorators/guards:
  - `login_required`
  - `admin_required`
- לשמור ב־session רק מידע מינימלי:
  - `uid`
  - `email`
  - `role`
  - `token expiry`
- להוסיף token refresh/logout מסודר.
- כל הראוטים הקיימים (`/home`, `/sms`, `/bot`, `/record`, API endpoints) יעברו להשתמש ב־guards החדשים במקום `session["logged_in"]`.

### 5. Roles ו־custom claims
- להגדיר מודל הרשאות פשוט:
  - `role=admin`
  - `role=user`
- ה־role יישמר ב־custom claims דרך Admin SDK.
- בעת login השרת יקרא claims ויחליט איזה מסכים להציג.
- `admin@nimbusip.com` יאותחל כאדמין ראשון באמצעות bootstrap script/command חד־פעמי, לא דרך UI ציבורי.
- להגדיר policy ברורה:
  - משתמש ללא claim מפורש יקבל `user`
  - שינוי claim יחייב refresh session/token כדי להיכנס לתוקף

### 6. רה־ארגון backend עבור יכולות admin
- לפצל את `app.py` ללוגיקה ברורה לפחות ברמת מודולים:
  - `auth`
  - `admin_users`
  - `audit`
  - `existing business services`
- להוסיף API endpoints אדמיניסטרטיביים:
  - `GET /admin/users`
  - `POST /admin/users`
  - `POST /admin/users/<uid>/disable`
  - `POST /admin/users/<uid>/reset-password`
  - `POST /admin/users/<uid>/role`
  - `GET /admin/audit`
  - `GET /admin/audit/export`
- כל endpoints האדמיניים יהיו מוגנים ב־`admin_required`.
- כל פעולה אדמינית תכתוב audit event אפליקטיבי מובנה בנוסף ללוגי GCP.

### 7. מסך Users לאדמין
- להוסיף שני מסכים חדשים בניווט:
  - `Users`
  - `Audit Log`
- קישורים אלו יוצגו רק אם `role=admin`.
- במסך `Users` לבנות:
  - טבלה עם pagination/search
  - סינון לפי email, status, created date
  - badge עבור `role`
  - badge עבור `enabled/disabled`
  - פעולות__הערות: `Create`, `Disable/Enable`, `Reset Password`, `Change Role`
- יצירת משתמש תתבצע מה־backend דרך Admin SDK:
  - email
  - password זמני או סיסמה שהאדמין מזין
  - role ראשוני
- איפוס סיסמה ב־v1:
  - ברירת מחדל מומלצת: generate password reset link דרך Admin SDK ולהציג/להחזיר אותו לאדמין או לשלוח מייל אם יוגדר SMTP בהמשך
  - אם לא רוצים דיוור כרגע, לתכנן UI שמציג “reset link generated”
- חיפוש/סינון יתבצע בצד השרת אם הרשימה עלולה לגדול; לא להישען על fetch של כל המשתמשים ללקוח בלי צורך.

## 8. מסך Audit Log לאדמין
- לבנות מסך שמאחד שני מקורות:
  - Cloud Logging עבור auth/platform/runtime events
  - audit events אפליקטיביים מובנים עבור פעולות__הערות admin
- ב־v1 להציג לפחות:
  - login succeeded
  - login failed
  - blocked by domain policy
  - user created
  - user disabled/enabled
  - role changed
  - password reset initiated
- לקרוא Cloud Logging עם פילטרים עבור:
  - `identitytoolkit.googleapis.com`
  - `run.googleapis.com`
  - לוגים אפליקטיביים עם payload מובנה
- במסך להוסיף:
  - טווח תאריכים
  - פילטר לפי משתמש
  - פילטר לפי action
  - export ל־CSV
- לנרמל את התצוגה למבנה אחיד:
  - timestamp
  - actor
  - target
  - action
  - status
  - metadata

### 9. אינסטרומנטציה ואחידות audit
- להוסיף helper אחיד לכתיבת audit events מהאפליקציה בפורמט JSON structured logging.
- כל פעולה רגישה חדשה תשתמש באותו helper.
- ב־v1 “critical app actions” לא יורחבו לכל הזרימות העסקיות של SMS/Bot/Recordings, אלא רק לפעולות__הערות admin + auth events, בהתאם להחלטה שננעלה.
- להכין extension point כדי להוסיף בעתיד גם audit על:
  - יצירת SMS
  - סימון done
  - פעולות__הערות recordings
  - פעולות__הערות bot

### 10. UI / Navigation / UX
- לעדכן את כל ה־templates הקיימים כך שהניווט יהיה role-aware.
- להוסיף ל־sidebar/menu:
  - `Dashboard`
  - `SMS`
  - `Bot`
  - `Recordings`
  - `Users` רק admin
  - `Audit Log` רק admin
- במסך login:
  - לשנות copy מ־“Use your service account” ל־copy שמתאים ל־Identity Platform
  - להציג הודעות שגיאה אחידות
  - להכין מצב future ל־forgot password אם יתווסף
- לשמור על visual language קיים של `nav.css` וה־templates, בלי להכניס framework frontend חדש ב־v1.

### 11. בדיקות ואימות
- להוסיף בדיקות unit/integration עבור:
  - login success עם domain תקין
  - login reject עבור domain לא תקין
  - session creation ו־logout
  - access deny לראוט admin עבור `user`
  - access allow לראוט admin עבור `admin`
  - create user / disable / role change endpoints
  - audit event emission
- להוסיף smoke tests ידניים ל־Cloud Run staging:
  - `admin@nimbusip.com` נכנס ורואה `Users` + `Audit`
  - משתמש רגיל רואה רק מסכים רגילים
  - אימייל לא מהדומיין נחסם
  - שינוי role נכנס לתוקף לאחר re-login/refresh
  - export CSV במסך audit
- לעדכן acceptance criteria כך שכל flow קריטי יאומת גם ב־UI וגם ב־API.

## Public APIs / Interfaces / Types
- ראוטים חדשים:
  - `/auth/login`
  - `/logout` מעודכן
  - `/admin/users`
  - `/admin/users/<uid>/disable`
  - `/admin/users/<uid>/reset-password`
  - `/admin/users/<uid>/role`
  - `/admin/audit`
  - `/admin/audit/export`
- session model חדש:
  - `uid: str`
  - `email: str`
  - `role: "admin" | "user"`
  - `authenticated_at`
  - `expires_at`
- audit event schema אחיד:
  - `timestamp`
  - `actor_email`
  - `actor_uid`
  - `target_email`
  - `target_uid`
  - `action`
  - `status`
  - `source`
  - `metadata`

## Test Plan
- משתמש עם `@nimbusip.com` ו־password תקין מצליח להיכנס.
- משתמש עם domain אחר נדחה גם אם ה־credential תקין.
- משתמש disabled לא יכול להיכנס.
- משתמש רגיל לא יכול לפתוח `/admin/users` או `/admin/audit`.
- אדמין יכול ליצור משתמש חדש עם role=`user`.
- אדמין יכול לשנות role של משתמש ל־`admin` ולהפך.
- אדמין יכול להשבית משתמש ולהחזיר לפעיל.
- reset password יוצר אירוע audit ומחזיר תוצאה צפויה.
- audit filters לפי תאריך/משתמש/פעולה עובדים נכון.
- export CSV מייצא את הרשומות המסוננות.

## Assumptions
- v1 נשאר Flask server-rendered + JS קיים, בלי מעבר ל־SPA או React.
- authentication מתבצע עם `Email/Password`, לא Google SSO.
- `admin@nimbusip.com` יוקם כאדמין ראשון באמצעות bootstrap חיצוני חד־פעמי.
- מסך audit ב־v1 מכסה auth events + admin actions בלבד; פעולות__הערות עסקיות של SMS/Bot/Recordings יישארו לשלב הבא.
- אם לא מוגדר מנגנון מייל ייעודי, reset password ב־v1 יתבסס על reset link ולא על דיוור custom.
- הריפקטור של `app.py` הוא חלק מהמשימה, כדי לא להטמיע auth/admin חדשים בתוך קובץ יחיד של 1000+ שורות.
