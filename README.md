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

Базовое покрытие Day 1:

- успешный `array_last`
- ошибка schema (`unknown operation`)
- ошибка expression для `array_filter.condition`
