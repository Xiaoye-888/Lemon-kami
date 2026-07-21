# App Versions Modern Clean Redesign

## Goal

Redesign the admin version update page as a modern, clean Windows release console. The approved direction is the `version-page-modern-clean-v5.html` mockup from the brainstorming companion: a current-version status strip, a focused version history table, and a right-side release workspace.

## Scope

This design applies to `admin/src/views/AppVersions.vue` and keeps the existing admin API contract unless implementation discovers a small read-only helper is needed.

The page is Windows-only. Remove platform switching from the version update UI and always create/update records with `platform: "windows"`.

## Page Structure

The page has three main zones.

1. Header

- App selector remains visible.
- Platform is shown as a locked `Windows` control, not an editable dropdown.
- Primary action is `新增版本`.
- Secondary action is `复制检查接口`.

2. Current release status strip

- Shows current effective Windows release: `version`, `version_code`, force-update state, and the rule `current_version_code < latest_version_code`.
- Shows the next suggested version code as the current highest Windows version code plus one.
- Shows the auto-generated default title for new versions.
- Includes a short rollback reminder: rollback packages must use a higher version code than the bad client version.

3. Main work area

- Left side is the version history table.
- Right side is a release workspace with a new-version draft summary and update-popup preview.

## Version History Table

Keep the table as the core work area, but reduce visual noise and remove low-value columns from the list view.

Columns:

- Version: version name plus version code.
- Status: draft, published, archived.
- Effective state: current effective, history, or not effective.
- Title / summary: update title plus one-line notes.
- Published time.
- Actions.

Actions:

- Published current version: edit, copy as new version, archive.
- Archived version: view, copy as rollback package.
- Draft version: continue editing, publish.
- Historical published version: view/edit, copy as new version, archive.

Effective-state calculation is frontend-derived from the loaded Windows records: the published record with the highest `version_code` is current effective. Draft and archived versions are never effective.

## New Version Defaults

When opening `新增版本`:

- `platform` defaults to `windows` and is not user-editable.
- `version_code` defaults to highest existing Windows `version_code + 1`, or `1` when no records exist.
- `title` defaults to `应用名 YYYY-MM-DD 更新内容`.
- The date uses the local/admin UI date in `YYYY-MM-DD` format.
- The title remains editable.
- Existing defaults for force update, URL type, button text, notes, download URL, and status can remain.

Example title for app `小柠檬助手` on `2026-07-21`:

```text
小柠檬助手 2026-07-21 更新内容
```

## Edit And Preview Behavior

The right-side workspace reflects the selected or draft version.

- When no row is selected, it previews the draft created by `新增版本`.
- When a row is selected for edit, it previews that row's update popup.
- Force update disables or visually de-emphasizes `稍后再说` in the preview.
- The preview should display title, version, version code, notes, and download button text.

## Validation And Messaging

Keep existing backend validation. Add clearer frontend warnings before save:

- Published force updates require a download URL.
- A newly published Windows version should normally have a version code greater than the current effective version.
- Editing an older record with a lower version code should warn that it will not trigger updates for clients already above that code.
- Rollback copy should explain that the copied record needs a higher version code to trigger already-updated clients.

Avoid visible instructional paragraphs in the main interface. Use compact hints, badges, disabled states, and warnings near the relevant controls.

## Data Flow

Load apps through the existing app list API.

Load version records through:

```http
GET /api/v1/admin/apps/{app_id}/updates?platform=windows
```

Create records through:

```http
POST /api/v1/admin/apps/{app_id}/updates
```

Update records through:

```http
PUT /api/v1/admin/apps/{app_id}/updates/{version_id}
```

Save payloads should include `platform: "windows"` even though the UI does not expose a platform picker.

## Visual Direction

Use the modern clean mockup direction:

- Light gray page background.
- White panels with subtle borders and 8-10px radii.
- Strong primary blue only for main actions and current effective markers.
- Minimal table borders.
- Status badges for state differentiation.
- Stable row heights and fixed action widths.
- Right-side workspace visible on desktop and stacked below the table on narrow screens.

Do not use large marketing-style hero content. This is an admin workflow page, so density, scanability, and predictable actions matter more than decoration.

## Testing

Frontend/static tests should cover:

- The version update page no longer exposes Android, macOS, or all-platform selection.
- New-version default title includes app name, a `YYYY-MM-DD` date, and `更新内容`.
- New-version default code uses the next highest Windows version code.
- Version payloads use `platform: "windows"`.
- Existing preview behavior keeps download URL on the download button.

Backend tests are not expected unless implementation changes backend behavior.
