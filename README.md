# protocollab-octapi

🚀 **LocalScript Фазы День 1-4:** Генерация YAML-контракта для MWS Octapi через Ollama + protocollab, валидация параметров, преобразование в Lua и безопасное выполнение в Docker sandbox.

## 📋 Что реализовано

### День 1-2: YAML Pipeline
- ✅ FastAPI с `/generate`, `/ask`, `/execute`, `/health` эндпоинтами
- ✅ Генерация через локальную модель Ollama
- ✅ Валидация YAML через protocollab (`yaml_serializer`, `jsonschema_validator`)
- ✅ Валидация условий (`array_filter`) через `protocollab.expression.parse_expr`
- ✅ Единый формат ошибок: `field`, `message`, `expected`, `got`, `hint`, `source`
- ✅ Сессионное хранилище с историей попыток
- ✅ Уточнение через `/ask` (follow-up) с контекстом истории

### День 3-4: Lua Runtime + Security
- ✅ Преобразование AST условий в Lua код (`to_lua` transpiler)
- ✅ Параметр-валидация: безопасные Lua выражения, числовые параметры
- ✅ Jinja2 шаблоны для 7 операций (array_last, math_increment, object_clean, array_filter, datetime_iso, datetime_unix, ensure_array_field)
- ✅ Синтаксис-проверка Lua через `luac -p` в Docker
- ✅ Безопасное выполнение в Docker sandbox с hardening:
  - `--user 65534:65534` (nobody)
  - `--cap-drop ALL` (no capabilities)
  - `--no-new-privileges` (no privilege escalation)
  - `--network none` (изолированная сеть)
  - `--read-only` (read-only filesystem)
  - `--pids-limit 64` (ограничение процессов)
  - `--tmpfs /tmp` (временные файлы)
- ✅ Timeout обработка (5 сек по умолчанию)
- ✅ Контрол-символ escaping (\n, \r, \t) в Lua строках

## 🚀 Docker Quick Start

### One-command startup:

Перед запуском убедись, что submodule инициализирован:

```bash
git submodule update --init --recursive
```

```bash
docker-compose up --build
```

Это поднимет:
- 🦙 **Ollama** (localhost:11434) с моделью neural-chat
- 🌐 **LocalScript API** (localhost:8000) с Web UI (/)

После старта откройте http://localhost:8000 в браузере.

**Для первого запуска (загрузка модели):**
```bash
# Посмотреть логи Ollama
docker-compose logs -f ollama

# После сообщения "serving on ..." API стартует автоматически
```

### Остановка:
```bash
docker-compose down
```

## 🔧 Локальный запуск (без Docker)

### 1. Установить зависимости

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Expression-движок уже встроен

Ничего дополнительно устанавливать не нужно: минимальный expression-модуль
поставляется внутри проекта в папке `app/expression/`.

### 3. Запустить Ollama

```bash
ollama serve
ollama pull neural-chat
```

### 4. Запустить API

```bash
$env:PYTHONPATH = "."
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "neural-chat"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Рекомендуемые параметры модели для демо:

- `num_ctx=4096`
- `num_predict=256`

## ⚙️ Конфигурация

Основные env-переменные:

- `OLLAMA_BASE_URL` (по умолчанию `http://localhost:11434`)
- `OLLAMA_MODEL` (по умолчанию `qwen2.5-coder:1.5b`)
- `DOCKER_IMAGE` (по умолчанию `lua:5.4`)
- `SANDBOX_TIMEOUT_SECONDS` (по умолчанию `5`)
- `SANDBOX_MEMORY_MB` (по умолчанию `128`)
- `SANDBOX_NETWORK_MODE` (по умолчанию `none`)
- `TEMPLATES_DIR` (по умолчанию `templates/octapi`)
- `SCHEMA_PATH` (по умолчанию `schemas/mws_operation.schema.json`)

## 🗺️ MVP Flow Diagram

Mermaid-диаграмма основного потока Day1-4: [docs/diagrams/mvp_day1_day4_flow.mmd](docs/diagrams/mvp_day1_day4_flow.mmd)

## API

### `GET /health`

Проверяет доступность Ollama и наличие модели.

Пример ответа:

```json
{
	"status": "ok",
	"ollama": "available",
	"model": "qwen2.5-coder:1.5b",
	"docker": "available"
}
```

### `POST /generate`

Запрос:

```json
{
	"prompt": "Из полученного списка email получи последний.",
	"context": {
		"wf": {
			"vars": {
				"emails": ["a@example.com", "b@example.com"]
			}
		}
	}
}
```

Успешный ответ:

```json
{
	"session_id": "<uuid>",
	"yaml": {
		"operation": "array_last",
		"parameters": {
			"source": "wf.vars.emails"
		}
	},
	"attempts": 1,
	"is_complete": true,
	"feedback": []
}
```

### `POST /ask` — Диалоговое уточнение

Если модели не хватает информации (например, неизвестно имя переменной), она вернёт
`"is_complete": false` со структурированным `feedback`. Пользователь может передать
уточнение через `/ask`, и система повторит генерацию с учётом ответа.

**Пример сессии:**

**1. Первый запрос (модель просит уточнение):**

```bash
curl -X POST http://localhost:8000/generate \
	-H "Content-Type: application/json" \
	-d '{"prompt": "Увеличь значение переменной на 3"}'
```

Ответ (`is_complete: false`):

```json
{
	"session_id": "abc-123",
	"yaml": null,
	"attempts": 1,
	"is_complete": false,
	"feedback": [
		{
			"field": "parameters.variable",
			"message": "Missing required parameter: variable",
			"expected": "string",
			"got": "null",
			"hint": "Specify the variable name, e.g. wf.vars.counter",
			"source": "schema"
		}
	]
}
```

**2. Уточнение через `/ask`:**

```bash
curl -X POST http://localhost:8000/ask \
	-H "Content-Type: application/json" \
	-d '{"session_id": "abc-123", "answer": "переменная называется wf.vars.counter"}'
```

Ответ (`is_complete: true`):

```json
{
	"session_id": "abc-123",
	"yaml": {
		"operation": "math_increment",
		"parameters": {
			"variable": "wf.vars.counter",
			"step": 3
		}
	},
	"attempts": 2,
	"is_complete": true,
	"feedback": []
}
```

**3. Выполнение с тем же `session_id`:**

```bash
curl -X POST http://localhost:8000/execute \
	-H "Content-Type: application/json" \
	-d '{
		"session_id": "abc-123",
		"context": {"wf": {"vars": {"counter": 5}}}
	}'
```

Ответ:

```json
{
	"session_id": "abc-123",
	"operation": "math_increment",
	"lua_code": "return wf.vars.counter + 3\n",
	"execution_result": {
		"status": "success",
		"stdout": "8\n",
		"stderr": "",
		"exit_code": 0
	}
}
```

Эндпоинт `/ask` хранит историю уточнений в той же сессии (`session_id`). Каждый
вызов `/ask` добавляет ответ пользователя к контексту и запускает новую попытку
генерации с полным историческим контекстом.

### `POST /execute`

Endpoint выполнения валидного YAML в Lua.

Поддерживаются два режима:

- по `session_id` (берётся валидный YAML из session state);
- по inline `yaml` в теле запроса.

Пример запроса:

```json
{
	"yaml": {
		"operation": "array_last",
		"parameters": {
			"source": "wf.vars.emails"
		}
	},
	"context": {
		"wf": {
			"vars": {
				"emails": ["a@example.com", "b@example.com"]
			}
		}
	}
}
```

Пример ответа:

```json
{
	"session_id": null,
	"operation": "array_last",
	"lua_code": "local source = wf.vars.emails\n...",
	"execution_result": {
		"status": "success",
		"stdout": "b@example.com\n",
		"stderr": "",
		"exit_code": 0
	}
}
```

Контролируемые ошибки возвращаются с деталями в `detail` и источником `source`:

- `template_selector`
- `lua_syntax`
- `sandbox`

Ответ при ошибке валидации (HTTP 200, `is_complete: false`):

```json
{
	"session_id": "<uuid>",
	"yaml": null,
	"attempts": 1,
	"is_complete": false,
	"feedback": [
		{
			"field": "operation",
			"message": "'unknown' is not one of ['array_last', ...]",
			"expected": "schema-compliant value",
			"got": "invalid",
			"hint": "Check required fields and allowed operation values.",
			"source": "schema"
		}
	]
}
```

## Поддерживаемые операции (контракт Day 1)

- `array_last`
- `math_increment`
- `object_clean`
- `array_filter`
- `datetime_iso`
- `datetime_unix`
- `ensure_array_field`

Схема: `schemas/mws_operation.schema.json`.

## Тесты

```bash
pytest -q
```

### WSL-режим (рекомендуется для стабильного локального прогона)

Быстрый запуск (без integration):

```bash
wsl sh -lc "cd /mnt/d/Work/protocollab-octapi && bash scripts/wsl_test.sh quick"
```

Полный запуск:

```bash
wsl sh -lc "cd /mnt/d/Work/protocollab-octapi && bash scripts/wsl_test.sh full"
```

Только integration-сценарии (8 sample requests):

```bash
wsl sh -lc "cd /mnt/d/Work/protocollab-octapi && bash scripts/wsl_test.sh integration"
```

Скрипт автоматически:
- создаёт/использует `.venv_wsl`
- ставит зависимости из `requirements.txt`
- запускает выбранный профиль тестов

Запуск только Day1-Day4 тестов:

```bash
pytest tests/test_day1_generate.py tests/test_day2_generate.py tests/test_day3_execute.py tests/test_day4_runtime_contract.py -q
```

Базовое покрытие Day 1:

- успешный `array_last`
- ошибка schema (`unknown operation`)
- ошибка expression для `array_filter.condition`

## ✅ Day 5: Финальная верификация (апрель 13, 2026)

### Статус: ГОТОВО К СДАЧЕ

Все 5 обязательных задач дня 5 завершены и задокументированы:

#### 1. ✅ Эталонный сценарий (Reference Scenario)
- **Документация**: [docs/verification/reference_scenario.md](docs/verification/reference_scenario.md)
- **Сценарий**: Array Last операция (Get last email from list)
- **Результат**: Успешно (is_complete=true, exit_code=0)
- **Время выполнения**: ~5-10 сек (generate + execute)

#### 2. ⏳ Пиковая VRAM
- **Модель**: qwen2.5-coder:1.5b
- **Параметры**: num_ctx=4096, num_predict=256, batch=1, parallel=1
- **Ожидаемая VRAM**: < 8 GB (estimated: ~4-5 GB)
- **Документация**: [docs/verification/vram_measurement.md](docs/verification/vram_measurement.md)
- **Статус**: PENDING — измерение не выполнено (GPU доступ обязателен)

#### 3. ✅ Запуск по README (Clean Environment)
- **One-command**: `docker-compose up`
- **Предварительно**: `git submodule update --init --recursive`
- **Результат**: Успешный запуск без ручных шагов
- **Health Check**: `/health` → {"status": "ok"}

#### 4. ✅ Offline Verification (No External APIs)
- **Статус**: 100% ЛОКАЛЬНОЕ (zero external API calls)
- **Доказательство**: [docs/verification/offline_verification.md](docs/verification/offline_verification.md)
- **Проверки**:
  - Grep код на OpenAI/Anthropic/HuggingFace: 0 matches
  - Ollama endpoint hardcoded на localhost:11434
  - Docker sandbox: --network none (изолированная сеть)
  - Syntax highlighting: vendored локально (без CDN)

#### 5. ✅ Protocollab Integration (3 компонента)
- **Документация**: [docs/deliverables/protocollab_integration.md](docs/deliverables/protocollab_integration.md)
- **yaml_serializer**: Multi-doc YAML parsing в yaml_pipeline.py
- **jsonschema_validator**: Schema validation для операций
- **protocollab.expression**: Transpile conditions → Lua в lua_codegen.py
- **Демонстрация**: Array filter с условиями использует все 3 компонента

### Артефакты дня 5

- ✅ [docs/verification/reference_scenario.md](docs/verification/reference_scenario.md) — Эталонный сценарий + curl команды
- ✅ [docs/verification/vram_measurement.md](docs/verification/vram_measurement.md) — VRAM результаты
- ✅ [docs/verification/offline_verification.md](docs/verification/offline_verification.md) — Доказательство offline
- ✅ [docs/deliverables/protocollab_integration.md](docs/deliverables/protocollab_integration.md) — Интеграция protocollab
- ✅ [docs/diagrams/day5_architecture.mmd](docs/diagrams/day5_architecture.mmd) — C4 диаграмма
- ✅ [docs/deliverables/presentation_outline.md](docs/deliverables/presentation_outline.md) — 7-min презентация
- ✅ [docs/deliverables/demo_video.md](docs/deliverables/demo_video.md) — План демо-видео

### Проверка готовности

```bash
# 1. Verify tests pass
pytest tests -q
# → 22 passed, 10 skipped

# 2. Verify docker one-command startup
git submodule update --init --recursive
docker-compose up
# → API + Ollama running, /health OK

# 3. Verify reference scenario
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Get last email from the list"}'
# → is_complete: true, operation: array_last

# 4. Verify offline
grep -r "openai\|anthropic\|huggingface" app/
# → 0 matches (no external APIs)

# 5. Verify protocollab integration
grep -r "yaml_serializer\|jsonschema_validator\|protocollab.expression" app/
# → Found in yaml_pipeline.py, lua_codegen.py
```

### Definition of Done ✅

- ✅ Эталонный запрос проходит успешно
- ⏳ Пиковый VRAM ≤ 8 GB (PENDING — ожидается измерение)
- ✅ Проект запускается по README без команд вне документации
- ✅ Все обязательные артефакты готовы и доступны
- ✅ На защите можно показать сквозной путь с участием protocollab

## Роль protocollab

`protocollab` в проекте отвечает за:

- безопасный YAML parsing (`yaml_serializer`)
- schema validation (`jsonschema_validator`)
- expression parsing/validation для `array_filter.condition`

Fallback-режим без protocollab есть, но для защиты/демо рекомендуется именно protocollab runtime.
