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
; Uninstall (version 43, Leon 21.11.2026 20:05): also deletes our own packages <VaM>\AddonPackages\d0n.AIBody.<n>.var
; (exactly that name pattern, top level of AddonPackages only; nothing else in the VaM folder is touched). The VaM
; folder is the launcher's remembered one (launcher.json) or the one this setup recorded.
; Version 44 (Leon 21.11.2026 20:39-21:02):
;  - the setup carries the package d0n.AIBody.<v>.var (/DVarFile=, built by tools/build_var.py in CI) and copies it to
;    <VaM>\AddonPackages (only when a folder with VaM.exe is known); the build fails without /DVarFile.
;  - at start it looks for an existing install (installed companion version, d0n.AIBody.<n>.var in AddonPackages) and
;    says so: same version = "already installed", OK reinstalls / repairs, Cancel stops; older = "Update from <old> to
;    <v>". Silent setups never ask (reinstall / update). Everything found is written to the setup log.
;  - task "Remove older AIBody packages" (on by default): deletes the other d0n.AIBody.<digits>.var before copying.
;  - a running AIBody Companion is ended with taskkill before the files are replaced (PrepareToInstall): its tray
;    windows refused Restart Manager's close request, so the v43 setup looped on "files in use".
;    CloseApplications=force stays as a fallback. SetupLogging=yes: %TEMP%\Setup Log <date> #<n>.txt for every run.
#ifndef AppVersion
  #define AppVersion "0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\AIBody Companion"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\installer"
#endif
#ifndef VarFile
  #error VarFile is not defined: build the package with tools/build_var.py and pass /DVarFile=<path of d0n.AIBody.<v>.var>
#endif
#if !FileExists(VarFile)
  #error VarFile does not exist
#endif
#define VarName ExtractFileName(VarFile)
#ifndef VarSha256
  #define VarSha256 ""
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
CloseApplications=force
SetupLogging=yes
RestartApplications=no
UninstallDisplayName=AIBody Companion
UninstallDisplayIcon={app}\AIBody Companion.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Start with Windows"; Flags: unchecked
Name: "removeoldvars"; Description: "Remove older AIBody packages (d0n.AIBody.<number>.var) from AddonPackages"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#VarFile}"; DestDir: "{code:AddonDir}"; Flags: ignoreversion; Check: HaveVamDir

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

const
  ThisVersion = '{#AppVersion}';
  ThisVar = '{#VarName}';
  ThisVarSha256 = '{#VarSha256}';

{ The uninstall key Inno writes for this AppId (per user): DisplayVersion, the recorded VaM folder. }
function UninstKey(): String;
begin
  Result := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + ExpandConstant('{#SetupSetting("AppId")}') + '_is1';
end;

{ Version 43: our own package files only: "d0n.AIBody." + digits + ".var" (not d0n.AIBodySession.*, not other names). }
function IsOwnVar(const Name: String): Boolean;
var
  Middle: String;
  I: Integer;
begin
  Result := False;
  if (Length(Name) <= Length('d0n.AIBody.') + Length('.var')) then exit;
  if CompareText(Copy(Name, 1, Length('d0n.AIBody.')), 'd0n.AIBody.') <> 0 then exit;
  if CompareText(Copy(Name, Length(Name) - 3, 4), '.var') <> 0 then exit;
  Middle := Copy(Name, Length('d0n.AIBody.') + 1, Length(Name) - Length('d0n.AIBody.') - 4);
  if Middle = '' then exit;
  for I := 1 to Length(Middle) do
    if (Middle[I] < '0') or (Middle[I] > '9') then exit;
  Result := True;
end;

{ The own packages directly in <VamDir>\AddonPackages (file names only). }
function OwnVars(const VamDir: String): TArrayOfString;
var
  Folder: String;
  Rec: TFindRec;
  N: Integer;
begin
  N := 0;
  SetArrayLength(Result, 0);
  if Trim(VamDir) = '' then exit;
  Folder := AddBackslash(Trim(VamDir)) + 'AddonPackages';
  if FindFirst(Folder + '\d0n.AIBody.*.var', Rec) then
  begin
    try
      repeat
        if ((Rec.Attributes and FILE_ATTRIBUTE_DIRECTORY) = 0) and IsOwnVar(Rec.Name) then
        begin
          SetArrayLength(Result, N + 1);
          Result[N] := Rec.Name;
          N := N + 1;
        end;
      until not FindNext(Rec);
    finally
      FindClose(Rec);
    end;
  end;
end;

function JoinNames(const Names: TArrayOfString): String;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to GetArrayLength(Names) - 1 do
  begin
    if Result <> '' then Result := Result + ', ';
    Result := Result + Names[I];
  end;
  if Result = '' then Result := 'none';
end;

{ Deletes our own packages in <VamDir>\AddonPackages except the file named Keep ('' = all). Logs every name. }
procedure DeleteOwnVars(const VamDir, Keep: String);
var
  Folder: String;
  Names: TArrayOfString;
  I, N: Integer;
begin
  Folder := AddBackslash(Trim(VamDir)) + 'AddonPackages';
  Names := OwnVars(VamDir);
  N := 0;
  for I := 0 to GetArrayLength(Names) - 1 do
    if CompareText(Names[I], Keep) <> 0 then
    begin
      N := N + 1;
      if DeleteFile(Folder + '\' + Names[I]) then
        Log('Deleted ' + Folder + '\' + Names[I])
      else
        Log('Could not delete ' + Folder + '\' + Names[I] + ' (VaM still running?)');
    end;
  if N = 0 then Log('No other d0n.AIBody.<n>.var in ' + Folder);
end;

{ The companion version this setup's AppId recorded (Inno writes DisplayVersion = AppVersion), '' = not installed. }
function InstalledVersion(): String;
begin
  if not RegQueryStringValue(HKCU, UninstKey(), 'DisplayVersion', Result) then Result := '';
  Result := Trim(Result);
end;

{ This version's package in AddonPackages: '' = not there, 'identical' (same SHA-256), 'different' (another build). }
function ThisVarState(const VamDir: String): String;
var
  Path, Sha: String;
begin
  Result := '';
  if Trim(VamDir) = '' then exit;
  Path := AddBackslash(Trim(VamDir)) + 'AddonPackages\' + ThisVar;
  if not FileExists(Path) then exit;
  Result := 'different';
  if ThisVarSha256 = '' then begin Result := 'present'; exit; end;
  try
    Sha := GetSHA256OfFile(Path);
  except
    Sha := '';
    Log('Could not read ' + Path + ': ' + GetExceptionMessage());
  end;
  if CompareText(Sha, ThisVarSha256) = 0 then Result := 'identical';
end;

{ Version 44 (Leon 21:02): say what is already there. Same version: OK = reinstall / repair, Cancel = stop.
  Older (or newer) companion: "Update from <old> to <new>", OK continues. Silent setups never ask (they reinstall). }
function CheckExistingInstall(): Boolean;
var
  Dir, Old, VarState, Parts, Text: String;
  Found: TArrayOfString;
  Same: Boolean;
begin
  Result := True;
  if VamDirParam <> '' then Dir := VamDirParam else Dir := SafeDetectVamDir();
  Old := InstalledVersion();
  Found := OwnVars(Dir);
  VarState := ThisVarState(Dir);
  if Old = '' then Log('Existing install: AIBody Companion not installed') else Log('Existing install: AIBody Companion ' + Old);
  if Dir = '' then Log('Existing install: no VaM folder found yet')
  else Log('Existing install: AIBody packages in ' + AddBackslash(Dir) + 'AddonPackages: ' + JoinNames(Found)
           + '; ' + ThisVar + ': ' + VarState);
  Same := (Old = ThisVersion) or ((Old = '') and (VarState <> ''));
  if Same then
  begin
    Parts := '';
    if Old = ThisVersion then Parts := 'AIBody Companion ' + Old;
    if VarState <> '' then
    begin
      if Parts <> '' then Parts := Parts + ' and ';
      Parts := Parts + 'the package ' + ThisVar + ' in AddonPackages';
      if VarState = 'different' then Parts := Parts + ' (a different build)';
    end;
    Log('Existing install: same version ' + ThisVersion + ' (' + Parts + ')');
    Text := 'AIBody ' + ThisVersion + ' is already installed (' + Parts + ').' + #13#10#13#10 +
      'OK: reinstall / repair. AIBody Companion is closed if it is running, its files and the package ' + ThisVar +
      ' are replaced.' + #13#10 + 'Cancel: stop the setup and change nothing.';
  end
  else if Old <> '' then
  begin
    if StrToIntDef(Old, 0) < StrToIntDef(ThisVersion, 0) then
      Text := 'Update from AIBody ' + Old + ' to ' + ThisVersion + '.'
    else
      Text := 'AIBody Companion ' + Old + ' is installed; this setup installs version ' + ThisVersion + ' over it.';
    Log('Existing install: ' + Text);
    Text := Text + #13#10#13#10 + 'AIBody Companion is closed if it is running and replaced, and the package ' + ThisVar +
      ' is copied to AddonPackages.';
    if VarState <> '' then Text := Text + ' (It is already there and will be replaced.)';
    if GetArrayLength(Found) > 0 then
      Text := Text + #13#10#13#10 + 'AIBody packages in AddonPackages now: ' + JoinNames(Found) + '. ' +
        'Keep "Remove older AIBody packages" checked on the next page to delete the older ones.';
    Text := Text + #13#10#13#10 + 'OK: continue. Cancel: stop the setup and change nothing.';
  end
  else
  begin
    Log('Existing install: none (new install)');
    exit;
  end;
  if WizardSilent() then
  begin
    Log('Existing install: silent setup, continuing without asking (reinstall / update)');
    exit;
  end;
  if MsgBox(Text, mbConfirmation, MB_OKCANCEL) <> IDOK then
  begin
    Log('Existing install: the user chose Cancel; nothing was changed');
    Result := False;
  end
  else
    Log('Existing install: the user chose OK');
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
    exit;
  end;
  Result := CheckExistingInstall();
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
  if CurStep = ssInstall then
  begin
    Dir := ChosenVamDir();
    if not IsVamDir(Dir) then exit;
    if WizardIsTaskSelected('removeoldvars') then
    begin
      Log('Remove older AIBody packages: on; found ' + JoinNames(OwnVars(Dir)) + '; keeping ' + ThisVar);
      DeleteOwnVars(Dir, ThisVar);
    end
    else
      Log('Remove older AIBody packages: off; kept ' + JoinNames(OwnVars(Dir)));
    exit;
  end;
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

{ [Files]: the package goes to <VaM>\AddonPackages, only for a folder with VaM.exe. }
function AddonDir(Param: String): String;
begin
  Result := AddBackslash(ChosenVamDir()) + 'AddonPackages';
end;

function HaveVamDir(): Boolean;
begin
  Result := IsVamDir(ChosenVamDir());
  if Result then Log('Package: copying ' + ThisVar + ' to ' + AddonDir(''))
  else Log('Package: no VaM folder known, ' + ThisVar + ' is not copied (put it into <VaM>\AddonPackages yourself)');
end;

{ Version 44: AIBody Companion's tray windows refuse Restart Manager's close request (v43 looped on "files in use"),
  so end it here, before any file is replaced. taskkill exit code 128 = no such process (left). }
procedure StopCompanion();
var
  Code, I: Integer;
begin
  for I := 1 to 20 do
  begin
    if not Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "AIBody Companion.exe"', '', SW_HIDE,
                ewWaitUntilTerminated, Code) then
    begin
      Log('Stop AIBody Companion: taskkill could not be started');
      exit;
    end;
    Log('Stop AIBody Companion: taskkill /F /T /IM "AIBody Companion.exe" exit code ' + IntToStr(Code));
    if Code = 128 then
    begin
      if I > 1 then Sleep(500);   { let Windows release the files of the ended process }
      exit;
    end;
    Sleep(250);
  end;
  Log('Stop AIBody Companion: still running after 20 tries; Restart Manager (CloseApplications=force) is next');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  StopCompanion();
end;

{ Uninstall: the VaM folder from launcher.json (removed later by [UninstallDelete]) or the one the setup recorded. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Dir: String;
begin
  if CurUninstallStep <> usUninstall then exit;
  Dir := LauncherVamDir();
  if not IsVamDir(Dir) then
    if not RegQueryStringValue(HKCU, UninstKey(), 'Inno Setup CodeFile: VamDir', Dir) then Dir := '';
  if IsVamDir(Dir) then
    DeleteOwnVars(Dir, '')
  else
    Log('Uninstall: no VaM folder known; no AIBody package deleted.');
end;
