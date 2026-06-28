from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from planner.proposal import generate_proposals


ROOT = Path(__file__).resolve().parents[1]


class PlanWeekRendererTests(unittest.TestCase):
    def test_format_proposal_handles_optional_trace_properties(self) -> None:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell is None:
            self.skipTest("PowerShell is not available")
        proposal = generate_proposals(dt.date(2026, 6, 29), 1, root=ROOT)[0]
        with tempfile.TemporaryDirectory() as temporary:
            proposal_path = Path(temporary) / "proposal.json"
            proposal_path.write_text(
                json.dumps(proposal),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-File",
                    str(ROOT / "tests" / "format-proposal-smoke.ps1"),
                    "-PlannerScript",
                    str(ROOT / "scripts" / "plan-week.ps1"),
                    "-ProposalJson",
                    str(proposal_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
