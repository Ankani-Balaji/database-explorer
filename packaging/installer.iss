; Inno Setup script: builds release\DatabaseExplorer-Setup-<version>.exe from the PyInstaller
; folder release\DatabaseExplorer. Run through packaging\build.ps1 (it passes the version).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Keep this AppId forever: it's how Windows recognises upgrades of the same app
AppId={{7C2E4B1A-5D3F-4E8B-9A61-2F0C8D4E7B35}
AppName=Database Explorer
AppVersion={#AppVersion}
AppVerName=Database Explorer {#AppVersion}
AppPublisher=Ankani-Balaji
AppPublisherURL=https://github.com/Ankani-Balaji/database-explorer
AppSupportURL=https://github.com/Ankani-Balaji/database-explorer/issues
AppUpdatesURL=https://github.com/Ankani-Balaji/database-explorer/releases
; Installs for the current user only: no administrator rights needed
PrivilegesRequired=lowest
DefaultDirName={autopf}\Database Explorer
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\release
OutputBaseFilename=DatabaseExplorer-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\DatabaseExplorer.exe
UninstallDisplayName=Database Explorer
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Database Explorer installer
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Close a running copy before upgrading
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove files from an older version before copying the new ones
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\release\DatabaseExplorer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Database Explorer"; Filename: "{app}\DatabaseExplorer.exe"; Comment: "Browse your local PostgreSQL and MySQL databases"
Name: "{autodesktop}\Database Explorer"; Filename: "{app}\DatabaseExplorer.exe"; Comment: "Browse your local PostgreSQL and MySQL databases"; Tasks: desktopicon

[Run]
Filename: "{app}\DatabaseExplorer.exe"; Description: "{cm:LaunchProgram,Database Explorer}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the app if it's running, so its files can be removed
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im DatabaseExplorer.exe"; Flags: runhidden; RunOnceId: "StopApp"

[UninstallDelete]
; Logs and the app window's saved settings
Type: filesandordirs; Name: "{localappdata}\DatabaseExplorer"
