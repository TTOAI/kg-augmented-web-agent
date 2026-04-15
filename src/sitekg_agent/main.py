"""sitekg-agent CLI 진입점.

WebArena-Verified 어댑터를 호출하여 task 하나를 실행한다.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sitekg-agent",
        description="WebArena-Verified 어댑터를 통해 task 하나를 실행한다",
    )
    parser.add_argument("--tasks-file", required=True, help="task 데이터가 들어 있는 JSON 파일 경로")
    parser.add_argument("--task-id", type=int, required=True, help="실행할 task ID")
    parser.add_argument(
        "--run-root",
        default="output",
        help="벤치마크 실행 산출물을 저장할 루트 디렉터리",
    )
    parser.add_argument("--headed", action="store_true", help="브라우저를 headed 모드로 실행")
    parser.add_argument("--human", action="store_true", help="사람이 직접 브라우저를 조작하는 human agent 모드")
    parser.add_argument("--storage-state-file", type=str, help="미리 생성된 Playwright storage state 파일 경로")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="URL/인증 설정용 환경 config JSON 경로",
    )
    return parser


async def _run_async(args: argparse.Namespace) -> int:
    from .adapters.webarena_verified import WebArenaVerifiedAdapter

    adapter = WebArenaVerifiedAdapter()
    config_path = Path(args.config) if args.config else None
    storage_state_file = Path(args.storage_state_file) if args.storage_state_file else None

    if args.human:
        return await adapter.run_task_human(
            tasks_file=Path(args.tasks_file),
            task_id=args.task_id,
            run_root=Path(args.run_root),
            config_path=config_path,
            storage_state_file=storage_state_file,
        )

    return await adapter.run_task(
        tasks_file=Path(args.tasks_file),
        task_id=args.task_id,
        run_root=Path(args.run_root),
        config_path=config_path,
        headed=args.headed,
        storage_state_file=storage_state_file,
    )


def cli() -> None:
    """콘솔 진입점."""
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(_run_async(args)))


if __name__ == "__main__":
    cli()
