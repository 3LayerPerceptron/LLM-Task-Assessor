"""
E2E tests — spin up the full Docker stack, run tests, tear down.

Requirements:
  - Docker and docker compose v2 installed
  - MISTRAL_API_KEY environment variable set

Run:
  MISTRAL_API_KEY=sk-... pytest -m e2e -v -s

The fixture builds images, starts all containers, waits for the backend
health endpoint, runs every test in this module, then does docker compose down.
"""
import os
import time
import subprocess
import pytest
import httpx

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "../../../backend-module/docker-compose.test.yml")
BASE_URL      = "http://localhost:18000/api/v1"
API_TOKEN     = "test-token"
HEALTH_URL    = f"{BASE_URL}/healthy"
STARTUP_TIMEOUT = 120   # seconds to wait for backend to become healthy
POLL_INTERVAL   = 3     # seconds between health-check attempts
RESULT_TIMEOUT  = 90    # seconds to wait for a grading result
RESULT_POLL     = 3     # seconds between result poll attempts


# ---------------------------------------------------------------------------
# Skip if no API key
# ---------------------------------------------------------------------------

if not os.environ.get("MISTRAL_API_KEY"):
    pytest.skip(
        "MISTRAL_API_KEY not set — skipping E2E tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compose(*args: str) -> subprocess.CompletedProcess:
    """Run a docker compose command against the test compose file."""
    cmd = [
        "docker", "compose",
        "-f", COMPOSE_FILE,
        "-p", "aigrader-e2e",
        *args,
    ]
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _wait_for_backend(timeout: int = STARTUP_TIMEOUT) -> None:
    """Poll the health endpoint until it returns 200 or timeout is reached."""
    deadline = time.time() + timeout
    last_err  = None
    while time.time() < deadline:
        try:
            r = httpx.get(HEALTH_URL, timeout=5)
            if r.status_code == 200:
                return
            last_err = f"HTTP {r.status_code}"
        except httpx.RequestError as exc:
            last_err = str(exc)
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Backend did not become healthy within {timeout}s. Last error: {last_err}"
    )


def _poll_result(submission_id: int, timeout: int = RESULT_TIMEOUT) -> dict:
    """Poll GET /aigrades?submissionid=X until ready=True or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = httpx.get(
            f"{BASE_URL}/aigrades",
            params={"submissionid": submission_id},
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("ready"):
            return data
        time.sleep(RESULT_POLL)
    raise TimeoutError(
        f"Grading result for submission {submission_id} "
        f"not ready within {timeout}s"
    )


def _submit(submission_id: int, content: str, task_description: str, max_grade: float = 10.0) -> dict:
    """POST a submission and return the parsed response."""
    r = httpx.post(
        f"{BASE_URL}/aigrades",
        json={
            "submission_id":    submission_id,
            "content":          content,
            "task_description": task_description,
            "max_grade":        max_grade,
        },
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Session-scoped Docker fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def docker_stack():
    """
    Build images and start the full docker-compose stack.
    Runs once for the entire E2E test session.
    """
    mistral_key = os.environ["MISTRAL_API_KEY"]
    env = {**os.environ, "MISTRAL_API_KEY": mistral_key}

    print("\n[e2e] Building and starting Docker stack...")
    subprocess.run(
        [
            "docker", "compose",
            "-f", COMPOSE_FILE,
            "-p", "aigrader-e2e",
            "up", "--build", "-d", "--wait",
        ],
        check=True,
        env=env,
    )

    print("[e2e] Waiting for backend to become healthy...")
    _wait_for_backend()
    print("[e2e] Backend is healthy. Running tests.")

    yield

    print("\n[e2e] Tearing down Docker stack...")
    _compose("down", "-v", "--remove-orphans")
    print("[e2e] Docker stack removed.")


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------

def test_e2e_health_check():
    """Backend health endpoint returns 200."""
    r = httpx.get(HEALTH_URL, timeout=5)
    assert r.status_code == 200


def test_e2e_auth_required():
    """Endpoints reject requests without a valid token."""
    r = httpx.post(f"{BASE_URL}/aigrades", json={
        "submission_id": 1,
        "content": "test",
        "task_description": "test",
        "max_grade": 10.0,
    }, timeout=5)
    assert r.status_code == 401

    r = httpx.get(f"{BASE_URL}/aigrades", params={"submissionid": 1}, timeout=5)
    assert r.status_code == 401


def test_e2e_full_pipeline():
    """
    Submit a real text answer → wait for Celery worker to grade it via
    the Mistral LLM → verify ready=True with grade and feedback.
    """
    submission_id = 10001

    resp = _submit(
        submission_id,
        content=(
            "Фотосинтез — это процесс, при котором растения используют "
            "солнечный свет, воду и углекислый газ для производства кислорода "
            "и энергии в форме глюкозы (6CO2 + 6H2O + свет → C6H12O6 + 6O2)."
        ),
        task_description="Объясните процесс фотосинтеза.",
        max_grade=10.0,
    )
    assert resp["submission_id"] == submission_id
    assert resp["status"] == "pending"

    result = _poll_result(submission_id)
    assert result["ready"] is True
    assert result["grade"] is not None
    assert 0.0 <= result["grade"] <= 10.0
    assert result["feedback"] and len(result["feedback"]) > 20


def test_e2e_poor_answer_low_grade():
    """A clearly incomplete answer should score below 50% of max grade."""
    submission_id = 10002
    max_grade     = 10.0

    _submit(
        submission_id,
        content="Не знаю.",
        task_description="Объясните процесс фотосинтеза подробно.",
        max_grade=max_grade,
    )

    result = _poll_result(submission_id)
    assert result["ready"] is True
    assert result["grade"] < max_grade * 0.6, (
        f"Expected low grade for a poor answer, got {result['grade']}"
    )


def test_e2e_grade_within_bounds():
    """Grade must always be within [0, max_grade]."""
    submission_id = 10003
    max_grade     = 5.0

    _submit(
        submission_id,
        content="Митохондрия — это органелла клетки, производящая энергию в виде АТФ.",
        task_description="Что такое митохондрия?",
        max_grade=max_grade,
    )

    result = _poll_result(submission_id)
    assert result["ready"] is True
    assert 0.0 <= result["grade"] <= max_grade, (
        f"Grade {result['grade']} is outside [0, {max_grade}]"
    )


def test_e2e_feedback_non_empty():
    """Feedback must be a real non-trivial string."""
    submission_id = 10004

    _submit(
        submission_id,
        content="Скорость света в вакууме ≈ 3×10^8 м/с. Это фундаментальная константа физики.",
        task_description="Какова скорость света?",
        max_grade=10.0,
    )

    result = _poll_result(submission_id)
    assert result["ready"] is True
    assert len(result["feedback"]) > 20, (
        f"Feedback too short: {result['feedback']!r}"
    )


def test_e2e_poll_unknown_submission_404():
    """Polling for a submission that was never submitted returns 404."""
    r = httpx.get(
        f"{BASE_URL}/aigrades",
        params={"submissionid": 99999},
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=5,
    )
    assert r.status_code == 404


def test_e2e_resubmit_regraded():
    """
    Resubmitting a better answer should produce a grade ≥ the first attempt.
    """
    submission_id = 10005

    _submit(
        submission_id,
        content="Не знаю что такое ДНК.",
        task_description="Объясните структуру ДНК.",
        max_grade=10.0,
    )
    first = _poll_result(submission_id)
    first_grade = first["grade"]

    _submit(
        submission_id,
        content=(
            "ДНК — двойная спираль из нуклеотидов, хранящая генетическую "
            "информацию. Состоит из двух цепей, связанных водородными связями "
            "между азотистыми основаниями (A-T, G-C)."
        ),
        task_description="Объясните структуру ДНК.",
        max_grade=10.0,
    )
    second = _poll_result(submission_id)
    second_grade = second["grade"]

    assert second["ready"] is True
    assert second_grade >= first_grade, (
        f"Better answer scored lower: {second_grade} < {first_grade}"
    )


def test_e2e_multiple_concurrent_submissions():
    """
    Submit several submissions at once and verify each gets an
    independent result.
    """
    cases = [
        (10010, "Вода состоит из молекул H2O.", "Что такое вода?", 5.0),
        (10011, "Земля вращается вокруг Солнца за 365 дней.", "Как Земля движется вокруг Солнца?", 5.0),
        (10012, "Не знаю.", "Объясните квантовую механику.", 5.0),
    ]

    for sid, content, task, max_g in cases:
        _submit(sid, content, task, max_g)

    results = {sid: _poll_result(sid) for sid, *_ in cases}

    for sid, _, _, max_g in cases:
        r = results[sid]
        assert r["ready"] is True, f"submission {sid} not ready"
        assert 0.0 <= r["grade"] <= max_g, f"submission {sid} grade out of range"

    # The "I don't know" answer (10012) should score lower than the real answers.
    assert results[10012]["grade"] <= results[10010]["grade"] or \
           results[10012]["grade"] <= results[10011]["grade"], \
        "Expected the 'I don't know' answer to score lower than at least one real answer"
