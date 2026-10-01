# ToDoFeatures

This file stores postponed feature work that should be easy to resume in a future session.

## Planned User Management Flow

- Authentication source of truth: Supabase Auth
- Email sending provider: Resend
- App-side authorization source: Supabase profile table
- Enforce scoped access on the Flask server, not only in the UI
- Initial account setup should use a login-styled page with one-time verification and password creation

## Example Scoped User

- Email: `mayan.cohen@hot.net.il`
- `group_id = 3`
- `group_code = hot`
- `allowed_pages = ["features_status"]`
- `landing_page = "/features-status"`
- `scope_type = "project_manager"`
- `scope_value = "מעין כהן"`
- `active = true`

## Planned Admin Capabilities

- Admin dashboard card for user management
- Create scoped users
- Assign groups and allowed pages
- Send one-time onboarding email through Resend
- Let invited users set their own password
