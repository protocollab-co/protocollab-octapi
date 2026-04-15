# protocollab-octapi

Локальный сервис для генерации структурированного контракта операции (operation + parameters), проверки валидности, генерации Lua-кода и безопасного выполнения в Docker sandbox.

## Что делает проект

По текстовой задаче сервис:

1. Генерирует структурированный контракт через локальную Ollama-модель.
2. Валидирует данные по схеме и правилам выражений.
3. Генерирует Lua из Jinja2-шаблонов.
4. Проверяет синтаксис Lua и выполняет код в изолированной песочнице.
5. Возвращает структурированный `feedback` для итеративного исправления через `/ask`.

Проект ориентирован на локальный/offline запуск и воспроизводимые demo-сценарии.

## Чеклист по условиям задачи

- ✅ Локальная open-source LLM через Ollama
- ✅ Отсутствие внешних AI-вендоров в runtime
- ✅ Генерация Lua-кода по запросу на естественном языке
- ✅ Минимум одна итерация уточнения/доработки (`/ask`)
- ✅ Проверяемая валидация результата (schema, expression, Lua syntax, sandbox)
- ✅ One-line запуск через `docker-compose up --build`
- ✅ C4-артефакт архитектуры в репозитории (`docs/diagrams/day5_architecture.mmd`)
- ✅ Подготовлены артефакты презентации и демо-видео (`docs/deliverables/`)
- ⏳ Подтвержденный peak VRAM <= 8 GB в `docs/verification/vram_measurement.md` (заполнить фактом измерения)

## Чеклист по нашим фичам

- ✅ Эндпоинты: `/health`, `/generate`, `/ask`, `/execute`
- ✅ Runtime-управление моделью: `/models`, `/models/select`
- ✅ Runtime-управление профилем генерации: `/profiles`, `/profiles/select`
- ✅ Двухфазная генерация: JSON (generate) -> YAML (follow-up)
- ✅ Единый формат ошибок: `field`, `message`, `expected`, `got`, `hint`, `source`
- ✅ Генерация Lua через Jinja2 шаблоны (`templates/octapi/*.jinja2`)
- ✅ Безопасный sandbox (Docker) + логирование runtime в `logs/runtime.log`
- ✅ UI с примерами, историей и визуальным статусом этапов
- ✅ Скрипт запуска `scripts/run_api_8888.sh` с авто-проверкой/подъемом Ollama

## Ключевые особенности

- Локальная инференс-модель через Ollama (`localhost:11434`).
- Двухфазная генерация:
  - первичная генерация в JSON-режиме,
  - автокоррекция/уточнение в YAML-режиме.
- Единый формат ошибок:
  - `field`, `message`, `expected`, `got`, `hint`, `source`.
- Поддержка 7 операций:
  - `array_last`
  - `math_increment`
  - `object_clean`
  - `array_filter`
  - `datetime_iso`
  - `datetime_unix`
  - `ensure_array_field`
- Безопасное выполнение Lua:
  - предварительная синтаксическая проверка,
  - изоляция в Docker с ограничениями.
- Web UI с примерами, историей, статусами пайплайна, выбором модели и профиля.
- Runtime-эндпоинты для моделей и профилей.

## Краткая архитектура

- API: `app/main.py`
- Валидация/нормализация: `app/services/yaml_pipeline.py`
- Генерация Lua: `app/services/lua_codegen.py` + `templates/octapi/*.jinja2`
- Песочница: `app/services/sandbox_executor.py`
- Сессии: `app/services/session_store.py`
- UI: `templates/index.html`

Диаграммы:

- `docs/diagrams/day5_architecture.mmd`
- `docs/diagrams/mvp_day1_day4_flow.mmd`

## API

Основные эндпоинты:

- `GET /health` — статус сервиса, модели и docker runtime.
- `POST /generate` — первичная генерация структурированного контракта.
- `POST /ask` — уточнение/исправление в рамках сессии.
- `POST /execute` — валидация + генерация Lua + выполнение.

Управление моделью/профилем в рантайме:

- `GET /models`
- `POST /models/select`
- `GET /profiles`
- `POST /profiles/select`

## Быстрый запуск (Docker)

1. Инициализируйте submodule:

```bash
git submodule update --init --recursive
```

2. Запустите стек:

```bash
docker-compose up --build
```

3. Откройте UI:

- http://localhost:8000

4. Остановка:

```bash
docker-compose down
```

## Локальный запуск (без docker-compose)

### Требования

- Python 3.11+
- Docker
- Ollama

### Установка зависимостей

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Запуск API-скриптом

```bash
./scripts/run_api_8888.sh
```

Скрипт:

- выставляет env-переменные по умолчанию,
- проверяет доступность Ollama,
- при необходимости пытается поднять `ollama serve`,
- запускает API на `8888`.

## Конфигурация

Ключевые переменные окружения:

- `OLLAMA_BASE_URL` (по умолчанию `http://localhost:11434`)
- `OLLAMA_MODEL` (по умолчанию `qwen2.5-coder:1.5b`)
- `SCHEMA_PATH` (по умолчанию `schemas/mws_operation.schema.json`)
- `TEMPLATES_DIR` (по умолчанию `templates/octapi`)
- `DOCKER_IMAGE`
- `SANDBOX_TIMEOUT_SECONDS`
- `SANDBOX_MEMORY_MB`
- `SANDBOX_NETWORK_MODE`

## Операции с моделями (Ollama)

Список установленных моделей:

```bash
curl -s http://localhost:11434/api/tags
```

Фоновая загрузка модели:

```bash
curl -N -sS -X POST http://localhost:11434/api/pull \
  -d '{"name":"deepseek-coder:6.7b","stream":true}'
```

Переключение активной модели для API:

```bash
curl -sS -X POST http://127.0.0.1:8888/models/select \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5-coder:1.5b"}'
```

Удаление модели из Ollama:

```bash
curl -sS -X DELETE http://localhost:11434/api/delete \
  -d '{"name":"qwen2.5-coder:1.5b-strict"}'
```

## Обязательный блок для жюри

Эталонная модель для проверки:

```bash
ollama pull qwen2.5-coder:1.5b
```

Фиксированные параметры генерации (заданы в коде):

- `num_ctx=4096`
- `num_predict=256`
- `batch=1`
- `parallel=1`

Источник параметров: `app/services/ollama_client.py`.

## Предсдачный чеклист

Перед отправкой в жюри проверьте:

1. One-line запуск работает:

```bash
docker-compose up --build
```

2. Локальная модель доступна:

```bash
curl -s http://localhost:11434/api/tags
```

3. API здоров:

```bash
curl -s http://localhost:8000/health
```

4. Эталонный сценарий проходит:

```bash
curl -sS -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Get last email from the list"}'
```

5. Верификация VRAM заполнена фактами измерений (`nvidia-smi`), не `PENDING`:

- `docs/verification/vram_measurement.md`

## Тестирование

Базовый запуск:

```bash
pytest -q tests
```

Фокусный прогон Day1-Day4:

```bash
pytest -q tests/test_day1_generate.py tests/test_day2_generate.py tests/test_day3_execute.py tests/test_day4_runtime_contract.py
```

Материалы по верификации:

- `docs/verification/reference_scenario.md`
- `docs/verification/offline_verification.md`
- `docs/verification/day5_delivery_checklist.md`

## Документация

Карта документации:

- `docs/README.md`

Рекомендуемые разделы:

- Runbook: `docs/ubuntu_runbook.md`
- Deliverables: `docs/deliverables/`
- Planning: `docs/planning/`
- История по дням: `docs/days/`
- Roadmap: `docs/roadmap/`

## Безопасность

Генерируемый код рассматривается как недоверенный вход. Для процедуры проверки, ограничений sandbox и итоговой верификации см.:

- `docs/verification/`
- `docs/deliverables/protocollab_integration.md`

## Примечание по лицензиям

Используемые модели и сторонние компоненты лицензируются отдельно.
Перед внешней поставкой проверьте условия лицензий в метаданных моделей и в `third_party/`.
