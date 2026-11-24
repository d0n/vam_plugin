"""Setup package handling after v44 (Don 21:25 and 22:25): the v44 setup deleted the older d0n.AIBody.<n>.var at
ssInstall, before any file was copied. When the install then failed or was cancelled, Inno's rollback removed the new
package as well and AddonPackages had no AIBody package at all. Now the older ones go only at ssPostInstall, after the
new package is in place with the bundled SHA-256; there is no option for it any more; a companion that cannot be ended
stops the setup in PrepareToInstall, before anything is changed."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
ISS = ROOT / "packaging" / "companion" / "AIBodyCompanion.iss"
WF = ROOT / ".github" / "workflows" / "companion-windows.yml"


def section(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


class PackageAfterInstallTests(TestCase):
    def setUp(self):
        self.iss = ISS.read_text(encoding="utf-8")

    def test_crlf_kept(self):
        raw = ISS.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))

    def test_nothing_deleted_before_the_copy(self):
        self.assertNotIn("ssInstall then", self.iss)
        step = section(self.iss, "procedure CurStepChanged", "\nend;")
        self.assertIn("if CurStep <> ssPostInstall then exit;", step)
        self.assertIn("PlacePackage(Dir);", step)
        self.assertLess(step.index("ssPostInstall"), step.index("PlacePackage(Dir);"))
        # the only DeleteOwnVars calls: after the check, and the uninstaller (all of ours)
        calls = [l.strip() for l in self.iss.splitlines() if "DeleteOwnVars(" in l and "procedure" not in l]
        self.assertEqual(sorted(calls), sorted(["DeleteOwnVars(Dir, ThisVar);", "DeleteOwnVars(Dir, '')"]))

    def test_new_package_checked_before_old_ones_go(self):
        check = section(self.iss, "function PackageInPlace", "\nend;")
        self.assertIn("FileExists(Path)", check)
        self.assertIn("GetSHA256OfFile(Path)", check)
        self.assertIn("CompareText(Sha, ThisVarSha256) = 0", check)
        place = section(self.iss, "procedure PlacePackage", "\nend;\n\nprocedure CurStepChanged")
        self.assertLess(place.index("if not PackageInPlace(NewVar) then"), place.index("DeleteOwnVars(Dir, ThisVar);"))
        failed = place[place.index("if not PackageInPlace(NewVar) then"):place.index("Log('Package: ' + NewVar + ' in place")]
        self.assertIn("Log('Package: ERROR ", failed)
        self.assertIn("older AIBody packages kept", failed)
        self.assertIn("if not WizardSilent() then", failed)
        self.assertIn("exit;", failed)
        self.assertNotIn("DeleteOwnVars", failed)

    def test_no_option_any_more(self):
        self.assertNotIn("removeoldvars", self.iss)
        self.assertNotIn("WizardIsTaskSelected", self.iss)
        self.assertNotIn('checked on the next page', self.iss)
        tasks = section(self.iss, "[Tasks]", "[Files]")
        self.assertEqual([l.split(";")[0] for l in tasks.splitlines()[1:] if l.strip()],
                         ['Name: "desktopicon"', 'Name: "autostart"'])

    def test_companion_kill_without_tree_and_stop_before_changes(self):
        self.assertNotIn("/F /T", self.iss)
        self.assertIn("'/F /IM \"AIBody Companion.exe\"'", self.iss)
        self.assertIn("CompanionStillRunning := True;", section(self.iss, "procedure StopCompanion", "\nend;"))
        prep = section(self.iss, "function PrepareToInstall", "\nend;")
        self.assertIn("CompanionStillRunning := False;", prep)
        self.assertLess(prep.index("StopCompanion();"), prep.index("if CompanionStillRunning then"))
        self.assertIn("Result := 'AIBody Companion is still running and could not be closed", prep)
        self.assertIn("Nothing was changed.", prep)

    def test_ci_failed_install_keeps_old_package(self):
        wf = WF.read_text(encoding="utf-8")
        self.assertIn("'taskkill /F /IM \"AIBody Companion.exe\" exit code 0'", wf)
        self.assertNotIn("/F /T", wf)
        case = wf[wf.index("# 4d."):wf.index("# 5.")]
        for part in ("[IO.File]::Open(", "'None'", '"/NOCLOSEAPPLICATIONS"', "if ($p.ExitCode -eq 0)",
                     "the older package was deleted although the install failed",
                     'Assert-Packages "after a failed install"', "(SHA-256 checked)"):
            self.assertIn(part, case)
        self.assertLess(case.index('"/NOCLOSEAPPLICATIONS"'), case.index('Assert-Packages "after a failed install"'))
