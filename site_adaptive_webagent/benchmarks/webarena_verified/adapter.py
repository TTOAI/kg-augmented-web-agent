from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import shutil
import sys
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

from site_adaptive_webagent.agent.core import run_agent
from site_adaptive_webagent.agent.types import AgentRunResult

logger = logging.getLogger("webarena_verified")

BENCHMARK_REQUIRED_TASK_KEYS = ("task_id", "intent_template_id", "sites", "start_urls", "intent")
BENCHMARK_REQUIRED_RESPONSE_KEYS = ("task_type", "status", "retrieved_data", "error_details")

NO_AUTH_SITES = {"wikipedia", "map"}
HEADER_LOGIN_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "shopping_admin": ("X-M2-Admin-Auto-Login", ("username",)),
    "shopping": ("X-M2-Customer-Auto-Login", ("email", "username")),
    "reddit": ("X-Postmill-Auto-Login", ("username",)),
}


class AgentInput(TypedDict):
    """`webarena-verified agent-input-get`가 export한 task payload."""

    task_id: int
    intent_template_id: int
    sites: list[str]
    start_urls: list[str]
    intent: str


def ensure_mapping_keys(payload: dict[str, Any], required_keys: tuple[str, ...], *, context: str) -> None:
    """dict에 필요한 키가 모두 있는지 검증한다."""
    missing = [key for key in required_keys if key not in payload]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{context}에 필요한 키가 없습니다: {missing_text}")


def validate_task_payload(payload: Any) -> AgentInput:
    """export된 benchmark task payload 하나를 검증한다."""
    if not isinstance(payload, dict):
        raise ValueError(f"task 항목은 JSON 객체여야 합니다. 현재 타입: {type(payload).__name__}")

    ensure_mapping_keys(payload, BENCHMARK_REQUIRED_TASK_KEYS, context="Task entry")

    sites = payload["sites"]
    start_urls = payload["start_urls"]
    if not isinstance(sites, list) or not all(isinstance(site, str) for site in sites):
        raise ValueError("task 항목의 'sites' 필드는 list[str] 이어야 합니다")
    if not isinstance(start_urls, list) or not all(isinstance(url, str) for url in start_urls):
        raise ValueError("task 항목의 'start_urls' 필드는 list[str] 이어야 합니다")
    if not isinstance(payload["intent"], str):
        raise ValueError("task 항목의 'intent' 필드는 문자열이어야 합니다")

    return payload  # type: ignore[return-value]


def validate_exported_tasks_file(tasks_file: Path) -> list[AgentInput]:
    """export된 tasks 파일이 어댑터 기대와 맞는지 검증한다."""
    if not tasks_file.exists():
        raise FileNotFoundError(f"tasks 파일을 찾을 수 없습니다: {tasks_file}")

    try:
        tasks_data = json.loads(tasks_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"tasks 파일에 잘못된 JSON이 들어 있습니다: {exc.msg}") from exc

    if not isinstance(tasks_data, list):
        raise ValueError(f"tasks 파일은 JSON 배열이어야 합니다. 현재 타입: {type(tasks_data).__name__}")

    return [validate_task_payload(task) for task in tasks_data]


def validate_agent_response_file(task_output_dir: Path) -> dict[str, Any]:
    """생성된 benchmark 응답 파일을 검증한다."""
    agent_response_path = task_output_dir / "agent_response.json"
    if not agent_response_path.exists():
        raise FileNotFoundError(f"agent response 파일이 없습니다: {agent_response_path}")

    payload = json.loads(agent_response_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("agent_response.json은 JSON 객체여야 합니다")

    ensure_mapping_keys(payload, BENCHMARK_REQUIRED_RESPONSE_KEYS, context="agent_response.json")
    if payload["task_type"] not in {"RETRIEVE", "MUTATE", "NAVIGATE"}:
        raise ValueError(f"agent_response.json에 지원하지 않는 task_type이 있습니다: {payload['task_type']!r}")
    if payload["status"] not in {
        "SUCCESS",
        "ACTION_NOT_ALLOWED_ERROR",
        "PERMISSION_DENIED_ERROR",
        "NOT_FOUND_ERROR",
        "DATA_VALIDATION_ERROR",
        "UNKNOWN_ERROR",
    }:
        raise ValueError(f"agent_response.json에 지원하지 않는 status가 있습니다: {payload['status']!r}")
    return payload


def validate_run_output(task_output_dir: Path) -> None:
    """benchmark evaluator가 기대하는 task 산출물을 검증한다."""
    validate_agent_response_file(task_output_dir)
    har_path = task_output_dir / "network.har"
    if not har_path.exists():
        raise FileNotFoundError(f"HAR 파일이 없습니다: {har_path}")
    if har_path.stat().st_size == 0:
        raise ValueError(f"HAR 파일이 비어 있습니다: {har_path}")


def backup_output_dir(task_output_dir: Path, task_id: int) -> None:
    """기존 task 출력 디렉터리가 있으면 백업한다."""
    if not task_output_dir.exists():
        return

    parent_dir = task_output_dir.parent
    idx = 1
    while True:
        backup_dir = parent_dir / f"{task_id}_bkp_{idx}"
        if not backup_dir.exists():
            break
        idx += 1

    shutil.move(str(task_output_dir), str(backup_dir))


def setup_task_logging(*, logger: logging.Logger, task_output_dir: Path) -> None:
    """표준 출력과 task별 로그 파일로 로깅을 설정한다."""
    log_file = task_output_dir / f"{logger.name.lower().replace('-', '_')}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # UTF-8 고정: Korean/intent 내 유니코드가 로그 파일에서 깨지지 않도록.
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    logger.info("로그 파일 경로: %s", log_file.resolve())


def add_runner_arguments(parser: argparse.ArgumentParser) -> None:
    """WebArena-Verified 러너용 CLI 인자를 추가한다."""
    parser.add_argument("--tasks-file", required=True, help="task 데이터가 들어 있는 JSON 파일 경로")
    parser.add_argument("--task-id", type=int, required=True, help="실행할 task ID")
    parser.add_argument(
        "--run-root",
        default="output",
        help="benchmark 실행 산출물을 저장할 루트 디렉터리",
    )
    parser.add_argument("--headed", action="store_true", help="브라우저를 headed 모드로 실행")
    parser.add_argument("--storage-state-file", type=str, help="미리 계산된 Playwright storage state 파일 경로")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="URL/인증 설정용 환경 config JSON 경로",
    )


def load_agent_input(tasks_file: Path, task_id: int) -> AgentInput:
    """`webarena-verified agent-input-get`가 export한 task 하나를 읽는다."""
    tasks_data = validate_exported_tasks_file(tasks_file)
    for task in tasks_data:
        if task["task_id"] == task_id:
            return task

    available_ids = [task["task_id"] for task in tasks_data]
    raise ValueError(f"tasks 파일에 task ID {task_id}가 없습니다. 사용 가능한 task ID: {available_ids}")


async def setup_storage_state(config_path: Path | None, task_output_dir: Path, agent_input: AgentInput) -> Path | None:
    """config 기반 로그인이 켜져 있을 때 인증 산출물을 준비한다."""
    if config_path is None:
        return None

    config = json.loads(config_path.read_text())
    storage_state_filename = config.get("storage_state_file_name", ".storage_state.json")
    auth_artifact_path = task_output_dir / storage_state_filename

    ui_login_sites, extra_headers = plan_auth_strategies(agent_input["sites"], config)

    if extra_headers:
        write_headers_sidecar(auth_artifact_path, extra_headers)

    if ui_login_sites:
        logger.info("다음 사이트에 대해 UI 로그인을 수행합니다: %s", ui_login_sites)
        await ui_login(
            sites=ui_login_sites,
            config=config,
            storage_state_file=auth_artifact_path,
        )

    if extra_headers or ui_login_sites:
        return auth_artifact_path

    return None


async def init_browser(
    playwright: Playwright,
    *,
    task_output_dir: Path,
    storage_state_file: Path | None,
    headed: bool,
) -> tuple[Browser, BrowserContext]:
    """benchmark 로깅에 맞게 Playwright browser/context를 생성한다."""
    browser = await playwright.chromium.launch(
        headless=not headed,
        slow_mo=500 if headed else 0,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )

    context_kwargs: dict[str, Any] = {
        "viewport": None,
        "no_viewport": True,
        "record_har_path": str(task_output_dir / "network.har"),
        "record_har_content": "embed",
    }

    if storage_state_file and storage_state_file.exists():
        context_kwargs["storage_state"] = str(storage_state_file)
        logger.info("storage state 사용 위치: %s", storage_state_file)

    context = await browser.new_context(**context_kwargs)

    if storage_state_file:
        headers_file = Path(str(storage_state_file) + ".headers.json")
        if headers_file.exists():
            headers = json.loads(headers_file.read_text())
            await context.set_extra_http_headers(headers)
            logger.info("%s개의 추가 헤더를 %s 에서 불러왔습니다", len(headers), headers_file)

    return browser, context


async def open_start_pages(context: BrowserContext, start_urls: list[str]) -> list[Page]:
    """task의 start URL들을 열고 생성된 페이지 목록을 반환한다."""
    pages: list[Page] = []
    for url in start_urls:
        page = await context.new_page()
        logger.info("%s 로 이동합니다", url)
        await page.goto(url)
        pages.append(page)
    return pages


def _maybe_load_kg_context(sites: list[str]) -> Any:
    """SITEKG_ENABLED=1이면 config/sites/<site>/에서 KGContext를 로드.

    Baseline 측정(env 미설정)에선 None 반환 → run_agent가 baseline 경로로 동작.
    KG 측정(SITEKG_ENABLED=1)에선 첫 site의 KG를 로드.
    로드 실패(설정 디렉토리 없음 등)는 로그만 남기고 None 반환(이중 안전).
    """
    import os
    if os.getenv("SITEKG_ENABLED") != "1":
        return None
    if not sites:
        return None
    try:
        from site_adaptive_webagent.agent.kg_integration import load_kg_context
        site = sites[0]
        ctx = load_kg_context(site)
        if ctx is None:
            logger.info("[KG] SITEKG_ENABLED=1 but no config for site=%s", site)
        else:
            logger.info("[KG] loaded KGContext for site=%s (infotypes=%d)",
                        site, len(ctx.kg.infotypes))
        return ctx
    except Exception:
        logger.exception("[KG] _maybe_load_kg_context failed — falling back to baseline")
        return None


def write_agent_response(task_output_dir: Path, result: AgentRunResult) -> Path:
    """최종 agent response를 benchmark 기대 형식으로 저장한다."""
    output_path = task_output_dir / "agent_response.json"
    payload = {
        "task_type": result.task_type,
        "status": result.status,
        "retrieved_data": result.retrieved_data,
        "error_details": result.error_details,
    }
    # UTF-8 강제 + ensure_ascii=False: retrieved_data나 error_details에 한글/비ASCII가 들어가도
    # 원문 보존. JSON 자체는 UTF-8 + Unicode escape 둘 다 유효하지만 사람 검토 편의상 원문을 쓴다.
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


async def ui_login(sites: list[str], config: dict[str, Any], storage_state_file: Path) -> None:
    """사이트 로그인 절차를 수행하고 Playwright storage state를 저장한다."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})

        try:
            for site_name in sites:
                environments = config.get("environments", {})
                env_config = resolve_environment_config(site_name, environments)

                urls = env_config.get("urls", [])
                active_url_idx = env_config.get("active_url_idx")
                if active_url_idx is not None and 0 <= active_url_idx < len(urls):
                    base_url = urls[active_url_idx]
                else:
                    base_url = urls[0] if urls else None

                if not base_url:
                    raise ValueError(f"사이트 '{site_name}'에 대해 활성 URL이 설정되지 않았습니다")

                credentials = env_config.get("credentials", {})
                username = credentials.get("username", "")
                password = credentials.get("password", "")

                login_handler = SITE_LOGIN_HANDLERS.get(site_name)
                if login_handler is None:
                    raise ValueError(f"사이트 '{site_name}'에 대한 로그인 핸들러가 없습니다")

                logger.info("사이트 '%s'에 대해 %s 에서 UI 로그인을 수행합니다", site_name, base_url)
                await login_handler(context, base_url, username, password)

            storage_state_file.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(storage_state_file))
            logger.info("storage state 저장 위치: %s", storage_state_file)
        finally:
            await context.close()
            await browser.close()


def plan_auth_strategies(
    sites: list[str],
    config: dict[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """환경 config를 바탕으로 사이트별 인증 전략을 결정한다."""
    environments = config.get("environments", {})
    ui_login_sites: list[str] = []
    extra_headers: dict[str, str] = {}

    for site_name in sites:
        env_config = resolve_environment_config(site_name, environments)
        use_header_login = bool(env_config.get("use_header_login", False))

        if site_name in NO_AUTH_SITES:
            logger.info("사이트 '%s'는 인증이 필요 없습니다", site_name)
            continue

        if use_header_login:
            header_name, header_value = build_header_login_header(site_name, env_config)
            extra_headers[header_name] = header_value
            logger.info("사이트 '%s'에 대해 '%s' 헤더 기반 로그인을 사용합니다", site_name, header_name)
        else:
            ui_login_sites.append(site_name)
            logger.info("사이트 '%s'에 대해 UI 로그인을 사용합니다", site_name)

    return ui_login_sites, extra_headers


def write_headers_sidecar(base_auth_file: Path, headers: dict[str, str]) -> Path:
    """러너가 읽는 sidecar 파일에 추가 HTTP 헤더를 저장한다."""
    headers_file = Path(str(base_auth_file) + ".headers.json")
    headers_file.parent.mkdir(parents=True, exist_ok=True)
    headers_file.write_text(json.dumps(headers, indent=2))
    logger.info("%s개의 헤더를 저장했습니다: %s", len(headers), headers_file)
    return headers_file


def resolve_environment_config(site_name: str, environments: dict[str, Any]) -> dict[str, Any]:
    """여러 키 변형 중 하나를 사용해 사이트 config를 찾는다."""
    candidates = [
        site_name.lower(),
        site_name.upper(),
        f"__{site_name.upper()}__",
        f"__{site_name.lower()}__",
    ]
    for candidate in candidates:
        env_config = environments.get(candidate)
        if env_config:
            return env_config
    raise ValueError(f"config에서 사이트 '{site_name}'의 환경 설정을 찾을 수 없습니다")


def build_header_login_header(site_name: str, env_config: dict[str, Any]) -> tuple[str, str]:
    """지원하는 사이트에 대해 header 기반 인증 항목을 만든다."""
    if site_name not in HEADER_LOGIN_SPECS:
        raise ValueError(
            f"사이트 '{site_name}'는 header 로그인 대상이 아닙니다. "
            "이 사이트는 UI 로그인을 사용하거나 사이트별 헤더 매핑을 추가하세요."
        )

    credentials = env_config.get("credentials", {})
    password = credentials.get("password")

    header_name, identity_keys = HEADER_LOGIN_SPECS[site_name]
    identity = next((credentials.get(key) for key in identity_keys if credentials.get(key)), None)

    if not identity or not password:
        raise ValueError(
            f"사이트 '{site_name}'의 header 로그인에는 "
            f"{identity_keys} 중 하나와 'password'가 필요합니다"
        )

    return header_name, f"{identity}:{password}"


async def shopping_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    page = await context.new_page()
    await page.goto(f"{base_url}/customer/account/login/")
    await page.get_by_label("Email", exact=True).fill(username)
    await page.get_by_label("Password", exact=True).fill(password)
    await page.get_by_role("button", name="Sign In").click()
    await page.close()


async def shopping_admin_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    page = await context.new_page()
    await page.goto(base_url)
    await page.get_by_label("Username").fill(username)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Sign in").click()
    await page.close()


async def gitlab_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    page = await context.new_page()
    await page.goto(f"{base_url}/users/sign_in")

    if username == "root":
        await page.get_by_test_id("username-field").click()
        await page.get_by_test_id("username-field").fill(username)
        await page.get_by_test_id("username-field").press("Tab")
        await page.get_by_test_id("password-field").fill(password)
        await page.get_by_test_id("sign-in-button").click()
    else:
        await page.get_by_label("Username or email").click()
        await page.get_by_label("Username or email").fill(username, timeout=3000)
        await page.get_by_label("Password").click()
        await page.get_by_label("Password").fill(password)
        await page.get_by_role("button", name="Sign in").click()

    await page.close()


async def reddit_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    page = await context.new_page()
    await page.goto(base_url)
    await page.get_by_role("link", name="Log in").click()
    await page.get_by_label("Username").fill(username)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Log in").click()
    await page.close()


async def wikipedia_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    del context, base_url, username, password
    logger.info("Wikipedia는 인증이 필요 없어 로그인을 건너뜁니다")


async def map_ui_login(context: BrowserContext, base_url: str, username: str, password: str) -> None:
    del context, base_url, username, password
    logger.info("지도 서비스는 인증이 필요 없어 로그인을 건너뜁니다")


SITE_LOGIN_HANDLERS = {
    "shopping": shopping_ui_login,
    "shopping_admin": shopping_admin_ui_login,
    "gitlab": gitlab_ui_login,
    "reddit": reddit_ui_login,
    "wikipedia": wikipedia_ui_login,
    "map": map_ui_login,
}


class WebArenaVerifiedAdapter:
    """WebArena-Verified 파일 계약을 처리하는 어댑터."""

    name = "webarena_verified"

    async def run_task(
        self,
        *,
        tasks_file: Path,
        task_id: int,
        run_root: Path,
        config_path: Path | None,
        headed: bool,
        storage_state_file: Path | None,
    ) -> int:
        """WebArena-Verified task 하나를 실행하고 벤치마크 호환 산출물을 저장한다."""
        from playwright.async_api import async_playwright

        task_output_dir = run_root / str(task_id)
        backup_output_dir(task_output_dir, task_id)
        task_output_dir.mkdir(parents=True, exist_ok=True)
        setup_task_logging(logger=logger, task_output_dir=task_output_dir)

        logger.info("webarena_verified 러너를 시작합니다")
        agent_input = load_agent_input(tasks_file, task_id)

        auth_artifact_path = storage_state_file
        if auth_artifact_path is None:
            auth_artifact_path = await setup_storage_state(config_path, task_output_dir, agent_input)

        result = AgentRunResult.unknown_error("agent did not run")

        async with async_playwright() as playwright:
            browser: Browser | None = None
            context: BrowserContext | None = None
            try:
                browser, context = await init_browser(
                    playwright,
                    task_output_dir=task_output_dir,
                    storage_state_file=auth_artifact_path,
                    headed=headed,
                )
                pages = await open_start_pages(context, agent_input["start_urls"])

                # SITEKG_ENABLED=1이면 KG-guided 동작, 아니면 baseline.
                # KG config는 config/sites/<site>/ 디렉토리에서 로드.
                kg_context = _maybe_load_kg_context(agent_input["sites"])

                result = await run_agent(
                    intent=agent_input["intent"],
                    sites=agent_input["sites"],
                    start_urls=agent_input["start_urls"],
                    task_id=agent_input["task_id"],
                    context=context,
                    pages=pages,
                    task_output_dir=task_output_dir,
                    kg_context=kg_context,
                )
                # NAVIGATE 성공 시 최종 URL을 다시 로드하여 HAR에 GET 요청 기록
                # (SPA의 pushState는 HAR에 기록되지 않으므로)
                if result.task_type == "NAVIGATE" and result.status == "SUCCESS" and pages:
                    try:
                        await pages[0].goto(pages[0].url, wait_until="load")
                    except Exception:
                        pass
            except Exception as e:
                logger.exception("에이전트 실행 실패: %s", e)
                result = AgentRunResult.unknown_error(str(e))
            finally:
                if context is not None:
                    await context.close()
                if browser is not None:
                    await browser.close()

        output_path = write_agent_response(task_output_dir, result)
        validate_run_output(task_output_dir)
        logger.info("agent response 저장 위치: %s", output_path.resolve())
        logger.info("HAR 파일 저장 위치: %s", (task_output_dir / "network.har").resolve())
        logger.info("webarena_verified 러너를 종료합니다")
        return 0

    async def run_task_human(
        self,
        *,
        tasks_file: Path,
        task_id: int,
        run_root: Path,
        config_path: Path | None,
        storage_state_file: Path | None,
    ) -> int:
        """Human agent 모드: 브라우저를 열고 사람이 직접 조작한 후 산출물을 저장한다."""
        from playwright.async_api import async_playwright

        task_output_dir = run_root / str(task_id)
        backup_output_dir(task_output_dir, task_id)
        task_output_dir.mkdir(parents=True, exist_ok=True)
        setup_task_logging(logger=logger, task_output_dir=task_output_dir)

        logger.info("webarena_verified human agent를 시작합니다")
        agent_input = load_agent_input(tasks_file, task_id)

        auth_artifact_path = storage_state_file
        if auth_artifact_path is None:
            auth_artifact_path = await setup_storage_state(config_path, task_output_dir, agent_input)

        logger.info("Intent: %s", agent_input["intent"])

        async with async_playwright() as playwright:
            browser: Browser | None = None
            context: BrowserContext | None = None
            try:
                browser, context = await init_browser(
                    playwright,
                    task_output_dir=task_output_dir,
                    storage_state_file=auth_artifact_path,
                    headed=True,
                )
                await open_start_pages(context, agent_input["start_urls"])

                logger.info("브라우저에서 태스크를 수동으로 수행하세요.")
                input(">>> 태스크 완료 후 Enter를 누르세요: ")
            finally:
                if context is not None:
                    await context.close()
                if browser is not None:
                    await browser.close()

        # agent_response 입력
        task_type_input = input(">>> Task type (NAVIGATE/RETRIEVE/MUTATE) [NAVIGATE]: ").strip().upper()
        task_type = task_type_input if task_type_input in ("NAVIGATE", "RETRIEVE", "MUTATE") else "NAVIGATE"
        retrieved_data = None
        if task_type == "RETRIEVE":
            data_input = input(">>> Retrieved data (추출한 값, 여러 개면 쉼표로 구분): ").strip()
            if data_input:
                retrieved_data = [v.strip() for v in data_input.split(",") if v.strip()]
        result = AgentRunResult(
            task_type=task_type,
            status="SUCCESS",
            retrieved_data=retrieved_data,
            error_details=None,
        )
        output_path = write_agent_response(task_output_dir, result)
        validate_run_output(task_output_dir)
        logger.info("agent response 저장 위치: %s", output_path.resolve())
        logger.info("HAR 파일 저장 위치: %s", (task_output_dir / "network.har").resolve())
        logger.info("webarena_verified human agent를 종료합니다")
        return 0
