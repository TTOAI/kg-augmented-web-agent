from __future__ import annotations

import argparse
import asyncio
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """WebArena-Verified 어댑터 러너용 CLI 파서를 생성한다."""
    parser = argparse.ArgumentParser(
        description="WebArena-Verified 어댑터를 통해 task 하나를 실행한다",
    )
    parser.add_argument("--tasks-file", required=True, help="task 데이터가 들어 있는 JSON 파일 경로")
    parser.add_argument("--task-id", type=int, required=True, help="실행할 task ID")
    parser.add_argument("--run-root", default="output", help="벤치마크 실행 산출물을 저장할 루트 디렉터리")
    parser.add_argument("--headed", action="store_true", help="브라우저를 headed 모드로 실행")
    parser.add_argument("--record-video", action="store_true",
                        help="task 수행 과정을 .webm로 녹화 (task_output_dir/video/)")
    parser.add_argument("--human", action="store_true", help="사람이 직접 브라우저를 조작하는 human agent 모드")
    parser.add_argument("--storage-state-file", type=str, help="미리 생성된 Playwright storage state 파일 경로")
    parser.add_argument("--config", type=str, default=None, help="URL/인증 설정용 환경 config JSON 경로")
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    from .adapter import WebArenaVerifiedAdapter

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
        record_video=args.record_video,
        storage_state_file=storage_state_file,
    )


def cli() -> None:
    """콘솔 진입점"""
    raise SystemExit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
