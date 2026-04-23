"""Fresh auth — WebArena-Verified의 ui_login 재활용해 새 storage state 생성."""
import asyncio
import json
from pathlib import Path

from site_adaptive_webagent.benchmarks.webarena_verified.adapter import ui_login


async def main():
    config_path = Path("config/webarena_verified.json")
    config = json.loads(config_path.read_text())
    out = Path("output/validation/.storage_state.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fresh login → {out}")
    await ui_login(sites=["gitlab"], config=config, storage_state_file=out)
    print(f"Saved: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
