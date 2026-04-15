from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from sitekg_agent.adapters.webarena_verified import (
    load_agent_input,
    validate_agent_response_file,
    validate_exported_tasks_file,
    validate_run_output,
)


class WebArenaVerifiedAdapterContractTests(unittest.TestCase):
    def test_validate_exported_tasks_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_path = Path(tmp_dir) / "tasks.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            "task_id": 44,
                            "intent_template_id": 303,
                            "sites": ["gitlab"],
                            "start_urls": ["http://localhost:8012"],
                            "intent": "Open my todos page",
                        }
                    ]
                )
            )

            tasks = validate_exported_tasks_file(tasks_path)

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["task_id"], 44)
            self.assertEqual(load_agent_input(tasks_path, 44)["intent"], "Open my todos page")

    def test_validate_run_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            (output_dir / "agent_response.json").write_text(
                json.dumps(
                    {
                        "task_type": "RETRIEVE",
                        "status": "SUCCESS",
                        "retrieved_data": ["value"],
                        "error_details": None,
                    }
                )
            )
            (output_dir / "network.har").write_text('{"log": {"entries": []}}')

            payload = validate_agent_response_file(output_dir)
            validate_run_output(output_dir)

            self.assertEqual(payload["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
