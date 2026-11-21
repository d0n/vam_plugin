; AIBody Companion installer (Inno Setup 6). Built by .github/workflows/companion-windows.yml:
;   ISCC /DAppVersion=<n> /DSourceDir=<PyInstaller onedir folder> /DOutputDir=<folder> AIBodyCompanion.iss
; Per-user install, no admin rights: %LOCALAPPDATA%\Programs\AIBody Companion. Settings of the launcher live in
; %LOCALAPPDATA%\AIBody Companion; the companion's config.json and log stay under <VaM>\Saves\PluginData\AIBody.
; VaM folder (Leon, 21.11.2026 17:01): a wizard page "Your VaM folder" asks for it, prefilled by auto-detection
; (the folder chosen at the last setup, the launcher's remembered folder, common places on every drive) and accepts
; only a folder with VaM.exe. The choice is written to %LOCALAPPDATA%\AIBody Companion\launcher.json ("vam_root"),
; which the launcher reads first, so the companion never has to sit inside the VaM folder. Silent setup:
; /VAMDIR="D:\VaM" (must contain VaM.exe, else setup stops with an error); without it the detected folder is used,
; or none is written and the app asks once with its folder picker.
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

[Code]
const
  LauncherFolder = '{localappdata}\AIBody Companion';
  LauncherFile = 'launcher.json';

var
  VamPage: TInputDirWizardPage;
  VamDirParam: String;

function IsVamDir(const Dir: String): Boolean;
begin
  Result := (Trim(Dir) <> '') and FileExists(AddBackslash(Trim(Dir)) + 'VaM.exe');
end;

{ "vam_root" of the launcher's launcher.json, if there is one (JSON written by the launcher or by this setup). }
function LauncherVamDir(): String;
var
  Text: AnsiString;
  S: String;
  P: Integer;
begin
  Result := '';
  if not LoadStringFromFile(ExpandConstant(LauncherFolder) + '\' + LauncherFile, Text) then exit;
  S := String(Text);
  P := Pos('"vam_root"', S);
  if P = 0 then exit;
  S := Copy(S, P + Length('"vam_root"'), Length(S));
  P := Pos('"', S);
  if P = 0 then exit;
  S := Copy(S, P + 1, Length(S));
  P := Pos('"', S);
  if P = 0 then exit;
  S := Copy(S, 1, P - 1);
  if Pos('\u', S) > 0 then exit;   { non-ASCII escapes: let detection find it instead }
  StringChangeEx(S, '\\', '\', True);
  Result := S;
end;

function DetectVamDir(): String;
var
  Subs: array of String;
  D, I: Integer;
  Root, Home: String;
begin
  Result := GetPreviousData('VamDir', '');
  if IsVamDir(Result) then exit;
  Result := LauncherVamDir();
  if IsVamDir(Result) then exit;
  SetArrayLength(Subs, 7);
  Subs[0] := 'VaM'; Subs[1] := 'Virt-A-Mate'; Subs[2] := 'VAM'; Subs[3] := 'Games\VaM';
  Subs[4] := 'Games\Virt-A-Mate'; Subs[5] := 'Program Files\VaM'; Subs[6] := 'Program Files\Virt-A-Mate';
  for D := Ord('C') to Ord('Z') do
  begin
    Root := Chr(D) + ':\';
    if DirExists(Root) then
      for I := 0 to GetArrayLength(Subs) - 1 do
        if IsVamDir(Root + Subs[I]) then
        begin
          Result := Root + Subs[I];
          exit;
        end;
  end;
  Home := GetEnv('USERPROFILE');
  if Home <> '' then
  begin
    if IsVamDir(Home + '\VaM') then begin Result := Home + '\VaM'; exit; end;
    if IsVamDir(Home + '\Desktop\VaM') then begin Result := Home + '\Desktop\VaM'; exit; end;
    if IsVamDir(Home + '\Downloads\VaM') then begin Result := Home + '\Downloads\VaM'; exit; end;
    if IsVamDir(Home + '\Games\VaM') then begin Result := Home + '\Games\VaM'; exit; end;
  end;
  Result := '';
end;

{ Detection must never stop the setup: any error is logged and the field stays empty (the user browses). }
function SafeDetectVamDir(): String;
begin
  try
    Result := DetectVamDir();
  except
    Log('VaM folder detection failed: ' + GetExceptionMessage());
    Result := '';
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  VamDirParam := Trim(ExpandConstant('{param:VAMDIR|}'));
  if (VamDirParam <> '') and not IsVamDir(VamDirParam) then
  begin
    Log('VAMDIR has no VaM.exe: ' + VamDirParam);
    SuppressibleMsgBox('The folder given with /VAMDIR has no VaM.exe:' + #13#10 + VamDirParam, mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

procedure InitializeWizard();
var
  Found: String;
begin
  VamPage := CreateInputDirPage(wpSelectTasks, 'Your VaM folder',
    'Where is Virt-A-Mate installed?',
    'AIBody Companion works with the VaM folder you choose here: the folder that contains VaM.exe. ' +
    'It was looked for automatically; check it, or click Browse to choose another one. ' +
    'You can change it later by running this setup again.',
    False, '');
  VamPage.Add('VaM folder (the folder with VaM.exe):');
  if VamDirParam <> '' then Found := VamDirParam else Found := SafeDetectVamDir();
  { The page refuses an empty field ("You must enter a full path with drive letter"), which aborts a silent setup.
    Nothing found: suggest <system drive>\VaM; Next still accepts only a folder with VaM.exe, a silent setup then
    writes nothing (ChosenVamDir checks VaM.exe again) and the app asks with its folder picker. }
  if Found = '' then
  begin
    Found := ExpandConstant('{sd}') + '\VaM';
    VamPage.SubCaptionLabel.Caption := 'Your VaM folder was not found automatically. ' +
      'Click Browse and choose the folder that contains VaM.exe. ' +
      'You can change it later by running this setup again.';
    Log('VaM folder not found; suggested: ' + Found);
  end
  else
    Log('VaM folder prefilled: ' + Found);
  VamPage.Values[0] := Found;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  { Silent: no page check and never a message box (one hung the CI install); ChosenVamDir takes /VAMDIR or the
    detection, and CurStepChanged writes launcher.json only for a folder with VaM.exe. }
  if WizardSilent() then exit;
  if (VamPage <> nil) and (CurPageID = VamPage.ID) and not IsVamDir(VamPage.Values[0]) then
  begin
    SuppressibleMsgBox('There is no VaM.exe in this folder:' + #13#10 + VamPage.Values[0] + #13#10#13#10 +
      'Please choose the folder that contains VaM.exe (for example C:\VaM).', mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

function ChosenVamDir(): String;
begin
  if WizardSilent() then
  begin
    if VamDirParam <> '' then Result := VamDirParam else Result := SafeDetectVamDir();
  end
  else
    Result := Trim(VamPage.Values[0]);
  Result := RemoveBackslashUnlessRoot(Result);
end;

function JsonEscape(const S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure WriteLauncherSettings(const Dir: String);
var
  Lines: TArrayOfString;
  Folder: String;
begin
  Folder := ExpandConstant(LauncherFolder);
  ForceDirectories(Folder);
  SetArrayLength(Lines, 4);
  Lines[0] := '{';
  Lines[1] := '  "vam_root": "' + JsonEscape(Dir) + '",';
  Lines[2] := '  "vam_root_set_by": "setup"';
  Lines[3] := '}';
  if SaveStringsToUTF8File(Folder + '\' + LauncherFile, Lines, False) then
    Log('VaM folder written to ' + Folder + '\' + LauncherFile + ': ' + Dir)
  else
    Log('Could not write ' + Folder + '\' + LauncherFile);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Dir: String;
begin
  if CurStep <> ssPostInstall then exit;
  Dir := ChosenVamDir();
  if IsVamDir(Dir) then
    WriteLauncherSettings(Dir)
  else
    Log('No VaM folder chosen or found; AIBody Companion asks with its folder picker on its first start.');
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'VamDir', ChosenVamDir());
end;
