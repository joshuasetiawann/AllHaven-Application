; ===========================================================================
; AllHaven — Windows installer (Inno Setup 6).
;
; Wraps the portable AllHaven-Setup.exe together with the application source
; that Docker Compose builds from, and registers the usual Windows furniture:
; Start Menu entry, optional desktop icon, and an uninstaller in
; Add/Remove Programs.
;
; Build:
;   1) python setup\windows\build_exe.py      (produces dist\AllHaven-Setup.exe)
;   2) ISCC setup\windows\AllHaven.iss        (produces dist\AllHaven-Installer-<ver>.exe)
;
; Installs per-user into %LOCALAPPDATA%, so no administrator rights are needed.
; Docker Desktop — which does need admin — is installed later by the wizard,
; after it asks.
; ===========================================================================

#define AppName "AllHaven"
#define AppPublisher "AllHaven"
#define AppExe "AllHaven-Setup.exe"
#define RepoRoot "..\.."
#define AppVersion Trim(FileRead(FileOpen(RepoRoot + "\VERSION")))

[Setup]
AppId={{7D1F4E62-3B4A-4C55-9E2C-AH4LLHAVEN001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#RepoRoot}\dist
OutputBaseFilename=AllHaven-Installer-{#AppVersion}
; lzma2/max shaved under a megabyte off a 9 MB payload while taking ~25 minutes
; to compile, which made every rebuild painful. Normal is the better trade.
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
; The payload is application source that Docker builds; keep it out of Program Files.
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
; The control panel / setup wizard.
Source: "{#RepoRoot}\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

; Compose definitions and the sources they build from.
Source: "{#RepoRoot}\docker-compose.prod.yml";       DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\docker-compose.prod.local.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\docker-compose.local.yml";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\docker-compose.yml";            DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\VERSION";                       DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\README.md";                     DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\.env.prod.example";             DestDir: "{app}"; Flags: ignoreversion

; No createallsubdirs here: it would recreate the excluded trees as empty folders,
; and an empty backend\.venv makes tooling believe a virtualenv is already set up.
Source: "{#RepoRoot}\backend\*";  DestDir: "{app}\backend";  Flags: ignoreversion recursesubdirs; \
    Excludes: ".venv\*,__pycache__\*,*.pyc,.pytest_cache\*,var\*,.env,.env.*"
Source: "{#RepoRoot}\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs; \
    Excludes: "node_modules\*,.next\*,out\*,.env,.env.*,android\build\*,android\.gradle\*"
Source: "{#RepoRoot}\deploy\*";   DestDir: "{app}\deploy";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\setup\*";    DestDir: "{app}\setup";    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Excludes: "__pycache__\*,*.pyc"
Source: "{#RepoRoot}\installer\*"; DestDir: "{app}\installer"; Flags: ignoreversion recursesubdirs createallsubdirs; \
    Excludes: "__pycache__\*,*.pyc"

[Icons]
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";      Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Set up and start {#AppName} now"; \
    WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Generated at runtime, so Inno does not track them.
Type: filesandordirs; Name: "{app}\dist"
Type: files;          Name: "{app}\.env.prod"
Type: files;          Name: "{app}\.env.prod.bak-*"

[Messages]
WelcomeLabel2=This installs [name/ver] on your computer.%n%nAllHaven runs entirely in Docker. If Docker Desktop is not installed yet, the setup wizard will offer to install it for you after this finishes.%n%nYour containers and database volumes are NOT removed when you uninstall.
