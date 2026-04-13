"""Integration tests for all 8 sample requests from localscript-openapi/sample_requests.md.

These tests require a running server (localhost:8000) and Ollama with the configured model.

Run with:
    pytest tests/test_all_samples.py -m integration -v

Skip automatically when the server/Ollama is not available.
"""

from __future__ import annotations

import pytest
import requests as _requests


BASE_URL = "http://localhost:8000"


def _is_server_available() -> bool:
    try:
        _requests.get(f"{BASE_URL}/health", timeout=2)
        return True
    except Exception:
        return False


def _is_ollama_running() -> bool:
    try:
        resp = _requests.get("http://localhost:11434", timeout=2)
        return resp.status_code < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sample data — all 8 examples from sample_requests.md
# ---------------------------------------------------------------------------
SAMPLES = [
    # 1. array_last — last element of email list
    {
        "name": "array_last",
        "prompt": "Из полученного списка email получи последний.",
        "context": {
            "wf": {
                "vars": {
                    "emails": ["user1@example.com", "user2@example.com", "user3@example.com"]
                }
            }
        },
        "expected_operation": "array_last",
        "expected_output": "user3@example.com",
    },
    # 2. math_increment — counter
    {
        "name": "math_increment",
        "prompt": "Увеличивай значение переменной try_count_n на каждой итерации.",
        "context": {"wf": {"vars": {"try_count_n": 3}}},
        "expected_operation": "math_increment",
        "expected_output": "4",
    },
    # 3. object_clean — remove ID, ENTITY_ID, CALL fields
    {
        "name": "object_clean",
        "prompt": (
            "Для полученных данных из предыдущего REST-запроса очисти значения "
            "ID, ENTITY_ID, CALL."
        ),
        "context": {
            "wf": {
                "vars": {
                    "RESTbody": {
                        "result": [
                            {
                                "ID": 123,
                                "ENTITY_ID": 456,
                                "CALL": "example_call_1",
                                "OTHER_KEY_1": "value1",
                                "OTHER_KEY_2": "value2",
                            },
                            {
                                "ID": 789,
                                "ENTITY_ID": 101,
                                "CALL": "example_call_2",
                                "EXTRA_KEY_1": "value3",
                            },
                        ]
                    }
                }
            }
        },
        "expected_operation": "object_clean",
        "expected_output": None,  # output is a table, check exit_code=0
    },
    # 4. datetime_iso — convert YYYYMMDD + HHMMSS to ISO 8601
    {
        "name": "datetime_iso",
        "prompt": "Преобразуй время из форматов YYYYMMDD и HHMMSS в строку ISO 8601.",
        "context": {
            "wf": {
                "vars": {
                    "json": {
                        "IDOC": {
                            "ZCDF_HEAD": {
                                "DATUM": "20231015",
                                "TIME": "153000",
                            }
                        }
                    }
                }
            }
        },
        "expected_operation": "datetime_iso",
        "expected_output": "2023-10-15T15:30:00",
    },
    # 5. ensure_array_field — ensure items is always array
    {
        "name": "ensure_array_field",
        "prompt": (
            "Преобразуй структуру так, чтобы все items в ZCDF_PACKAGES всегда были массивами."
        ),
        "context": {
            "wf": {
                "vars": {
                    "json": {
                        "IDOC": {
                            "ZCDF_HEAD": {
                                "ZCDF_PACKAGES": [
                                    {"items": [{"sku": "A"}, {"sku": "B"}]},
                                    {"items": {"sku": "C"}},
                                ]
                            }
                        }
                    }
                }
            }
        },
        "expected_operation": "ensure_array_field",
        "expected_output": None,  # complex structure, check exit_code=0
    },
    # 6. array_filter — filter items where Discount or Markdown is non-empty
    {
        "name": "array_filter",
        "prompt": (
            "Отфильтруй элементы массива, оставив только те, где есть значения в "
            "Discount или Markdown."
        ),
        "context": {
            "wf": {
                "vars": {
                    "parsedCsv": [
                        {"SKU": "A001", "Discount": "10%", "Markdown": ""},
                        {"SKU": "A002", "Discount": "", "Markdown": "5%"},
                        {"SKU": "A003", "Discount": None, "Markdown": None},
                        {"SKU": "A004", "Discount": "", "Markdown": ""},
                    ]
                }
            }
        },
        "expected_operation": "array_filter",
        "expected_output": None,  # filtered array, check exit_code=0 and stdout non-empty
    },
    # 7. Custom code — square of a number (no fixed template operation, check code executes)
    {
        "name": "custom_square",
        "prompt": "Добавь переменную с квадратом числа.",
        "context": {},
        "expected_operation": None,  # model may pick any operation; just check no crash
        "expected_output": None,
    },
    # 8. datetime_unix — convert ISO recallTime to Unix timestamp
    {
        "name": "datetime_unix",
        "prompt": "Конвертируй время в переменной recallTime в unix-формат.",
        "context": {
            "wf": {
                "initVariables": {
                    "recallTime": "2023-10-15T15:30:00+00:00"
                }
            }
        },
        "expected_operation": "datetime_unix",
        "expected_output": "1697380200",  # epoch for 2023-10-15T15:30:00Z
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate(session: _requests.Session, sample: dict) -> dict:
    resp = session.post(
        f"{BASE_URL}/generate",
        json={"prompt": sample["prompt"]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def _execute(session: _requests.Session, session_id: str, context: dict) -> dict:
    resp = session.post(
        f"{BASE_URL}/execute",
        json={"session_id": session_id, "context": context},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not _is_server_available() or not _is_ollama_running(),
    reason="Integration tests require a running server and Ollama",
)
@pytest.mark.parametrize("sample", SAMPLES, ids=[s["name"] for s in SAMPLES])
def test_sample_generate_and_execute(sample: dict) -> None:
    """For each sample: generate YAML, then execute Lua and verify output."""
    session = _requests.Session()

    # -- 1. Generate ---------------------------------------------------------
    gen_data = _generate(session, sample)

    assert gen_data.get("is_complete") is True, (
        f"[{sample['name']}] Generation incomplete after max attempts. "
        f"Feedback: {gen_data.get('feedback')}"
    )

    if sample["expected_operation"] is not None:
        assert gen_data["yaml"]["operation"] == sample["expected_operation"], (
            f"[{sample['name']}] Expected operation '{sample['expected_operation']}', "
            f"got '{gen_data['yaml']['operation']}'"
        )

    session_id: str = gen_data["session_id"]

    # -- 2. Execute ----------------------------------------------------------
    exec_data = _execute(session, session_id, sample["context"])
    result = exec_data.get("execution_result", {})

    assert result.get("status") == "success", (
        f"[{sample['name']}] Execution failed: "
        f"exit_code={result.get('exit_code')}, stderr={result.get('stderr')!r}"
    )

    if sample["expected_output"] is not None:
        stdout = result.get("stdout", "")
        assert sample["expected_output"] in stdout, (
            f"[{sample['name']}] Expected '{sample['expected_output']}' in stdout, "
            f"got: {stdout!r}"
        )
    else:
        assert result.get("exit_code") == 0, (
            f"[{sample['name']}] Non-zero exit code: {result.get('exit_code')}, "
            f"stderr={result.get('stderr')!r}"
        )
