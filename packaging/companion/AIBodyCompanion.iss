; AIBody Companion installer (Inno Setup 6). Built by .github/workflows/companion-windows.yml:
;   ISCC /DAppVersion=<n> /DSourceDir=<PyInstaller onedir folder> /DOutputDir=<folder> AIBodyCompanion.iss
; Per-user install, no admin rights: %LOCALAPPDATA%\Programs\AIBody Companion. Settings of the launcher live in
; %LOCALAPPDATA%\AIBody Companion; the companion's config.json and log stay under <VaM>\Saves\PluginData\AIBody.
#ifndef AppVersion
  #define AppVersion "0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\AIBody Companion"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\installer"
#endif

[Setup]
AppId={{7522ADEB-3287-40BF-92C0-136F44CA092B}
AppName=AIBody Companion
AppVersion={#AppVersion}
AppVerName=AIBody Companion {#AppVersion}
AppPublisher=d0n
AppPublisherURL=https://github.com/d0n/vam_plugin
DefaultDirName={localappdata}\Programs\AIBody Companion
DefaultGroupName=AIBody Companion
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AIBody Companion Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=AIBody Companion
UninstallDisplayIcon={app}\AIBody Companion.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Start with Windows"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AIBody Companion"; Filename: "{app}\AIBody Companion.exe"
Name: "{group}\Uninstall AIBody Companion"; Filename: "{uninstallexe}"
Name: "{userdesktop}\AIBody Companion"; Filename: "{app}\AIBody Companion.exe"; Tasks: desktopicon
Name: "{userstartup}\AIBody Companion"; Filename: "{app}\AIBody Companion.exe"; Tasks: autostart

[Run]
Filename: "{app}\AIBody Companion.exe"; Description: "Launch AIBody Companion now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""AIBody Companion.exe"""; Flags: runhidden; RunOnceId: "StopCompanion"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\AIBody Companion"
