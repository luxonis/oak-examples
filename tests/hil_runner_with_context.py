"""Run hil_runner with the selected reservation available on the synced testbed."""

import json
from pathlib import Path

from hil_framework.lib_testbed.tools import hil


def main():
    runner = hil.Hil(parse_and_run=False)
    runner.parse_args()

    class ContextWorkspaceSyncManager(hil.WorkspaceSyncManager):
        def check_and_sync_workspace(self, server):
            # The runner calls this hook after acquiring or reusing a reservation.
            artifacts_dir = Path(self.local_path) / ".artifacts"
            (artifacts_dir / "agent-logs").mkdir(parents=True, exist_ok=True)
            context = {
                "testbed": server.testbed_name,
                "reservation_name": runner.args.reservation_name,
            }
            (artifacts_dir / "hil-context.json").write_text(
                json.dumps(context), encoding="utf-8"
            )
            super().check_and_sync_workspace(server)

    original_manager = hil.WorkspaceSyncManager
    try:
        hil.WorkspaceSyncManager = ContextWorkspaceSyncManager
        runner.execute_hil()
    finally:
        hil.WorkspaceSyncManager = original_manager


if __name__ == "__main__":
    main()
