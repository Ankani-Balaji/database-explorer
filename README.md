<p align="center"><img src="packaging/logo.png" width="120" alt="Database Explorer logo"></p>

# Database Explorer

A read-only browser for the **PostgreSQL** and **MySQL** databases on your own computer.
Install it, click the desktop icon, and look through your tables — it works offline and never
changes your data.

## Download and install (Windows 10/11)

1. Open the **Releases** page of this repository (right-hand side of the repository page) and
   download **`DatabaseExplorer-Setup-<version>.exe`** from the latest release.
2. Open it. Windows may say **"Windows protected your PC"** because the app isn't signed with a
   paid certificate. Click **More info → Run anyway**.
3. Click **Next → Install** (no administrator rights needed). A **Database Explorer** icon
   appears on your desktop and in the Start menu.
4. Click the icon. The app opens in its own window. Log in to your database server (usually host
   `localhost`, with your PostgreSQL or MySQL username and password), pick a database, and explore.
5. Close the window when you're done — the app stops by itself.

To uninstall: **Settings → Apps → Installed apps → Database Explorer → Uninstall**.

Everything stays on your computer: the app only accepts connections from your own machine,
your password is only kept in memory while the app runs, and only the connection details
(never the password) are remembered for next time.

## Features

- Dashboard of tables **and views** with estimated row counts and sizes; sort by name, rows or size.
- Sidebar list of every table for quick switching; PostgreSQL schema switcher.
- Table data: search all columns, **filter per column** (contains; start with `=` for exact), **click a header to sort**, paging.
- **Foreign-key values are links** to the referenced row. **Click a row** to see every field in full (JSON pretty-printed, copy as JSON).
- **Structure tab**: columns (type, nullable, default, PK/FK), foreign keys, indexes.
- **Export CSV** of the current search/filters/sort (up to 50,000 rows).
- **SQL Console** (read-only): one statement at a time (SELECT, WITH, SHOW, EXPLAIN…), run in a read-only transaction that is always rolled back; shows up to 1,000 rows.
- Dark mode, and the address keeps page / search / sort / filters, so views can be bookmarked.

---

## For developers

React (Vite) frontend + Flask backend.

### Run from source (PowerShell)

Backend:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py               # http://localhost:5000
```

Frontend (new terminal):
```powershell
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

### Build the installer

Needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) once: `winget install JRSoftware.InnoSetup --scope user`

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Creates `release\DatabaseExplorer-Setup-<version>.exe` (from the app folder `release\DatabaseExplorer\`).
It uses its own build environment in `packaging\.venv`, so it doesn't touch `backend\venv`.
The logo is drawn by `packaging\make_icons.py`; the installer is defined in `packaging\installer.iss`.
Before a new release, bump the version in `backend\app.py` and `packaging\version_info.txt`.

### How the desktop app runs

- `backend\launcher.py` starts the server hidden (no console) on `127.0.0.1`, port 52300 or the next
  free one, and opens it in Microsoft Edge's app mode (its own window, with a separate profile in
  `%LOCALAPPDATA%\DatabaseExplorer\window`); without Edge it uses the default browser.
- Each window sends a heartbeat every 5 s and a goodbye when it closes. The app exits 6 s after the
  last window closes, 150 s after the last heartbeat if a browser crashes, or 2 minutes after
  starting if no window ever opens (`backend\lifecycle.py`).
- Starting it again while it runs just opens another window.
- Errors are shown as dialogs; the log is `%LOCALAPPDATA%\DatabaseExplorer\logs\app.log`.

### Tests

```powershell
cd backend; .\venv\Scripts\python.exe -m unittest discover -s tests -t .
```

### Notes

- Read-only: PostgreSQL read-only session, MySQL `SET SESSION TRANSACTION READ ONLY`.
- The server only answers on `127.0.0.1` and rejects requests whose host name isn't `localhost`/`127.0.0.1` (blocks DNS-rebinding attacks from other websites). The packaged app allows no cross-origin requests.
- Saved connections are forgotten after 8 hours unused (`CONNECTION_IDLE_HOURS`, `0` = never).
- Database connections are reused between requests (up to 4 per login, closed after 5 minutes idle).
- Tables over ~100,000 rows show an estimated total when nothing is filtered; **count exactly** gets the real number.
- Query timeout: 15 s (`QUERY_TIMEOUT_MS`, `0` = no limit).
- Debug mode is off by default; for development: `$env:FLASK_DEBUG = "1"; python app.py`.
- MySQL: schema = database name. PostgreSQL: schema defaults to `public`.
