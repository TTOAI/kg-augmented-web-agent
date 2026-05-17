from __future__ import annotations

import asyncio


def main() -> int:
    """루트 디렉터리에서 WebArena-Verified 러너 실행"""
    from site_adaptive_webagent.benchmarks.webarena_verified.runner import main as runner_main

    return asyncio.run(runner_main())


if __name__ == "__main__":
    raise SystemExit(main())
