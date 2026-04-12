# protocollab-octapi

Фазы Day 1-3: генерация YAML-контракта для MWS Octapi через Ollama, валидация через protocollab, затем безопасная трансляция в Lua и запуск в Docker sandbox.

## Что уже реализовано

- FastAPI backend с endpoint-ами:
	- `GET /health`
	- `POST /generate`
	- `POST /ask`
	- `POST /execute`
- Генерация YAML через локальную модель Ollama `qwen2.5-coder:1.5b`.
- Безопасный парсинг YAML через `yaml_serializer.SerializerSession`.
- Валидация контракта через `protocollab.jsonschema_validator`.
- Валидация `parameters.condition` для `array_filter` через `protocollab.expression.validate_expr`.
- Единый формат ошибки: `field`, `message`, `expected`, `got`, `hint`, `source`.
- Минимальный UI на одной странице (`/`) для демо потока.
- Строгий selector `operation -> lua template` без fallback для неизвестных операций.
- Для `array_filter` используется путь `protocollab.expression.parse_expr -> AST -> to_lua(ast)`.
- Проверка синтаксиса Lua через `luac -p` в Docker.
- Запуск Lua в sandbox Docker с ограничениями: timeout 5s, memory 128MB, `--network none`.

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Установка protocollab для патчей (рекомендуется):

```bash
git clone https://github.com/protocollab-co/protocollab.git third_party/protocollab
pip install -e ./third_party/protocollab
```

Если `protocollab` не установлен, сервис запустится в fallback-режиме:

- YAML: `PyYAML`
- Schema: `jsonschema`
- Expression: минимальная локальная проверка

Для хакатонной защиты рекомендуется запуск с установленным `protocollab`.

### 2. Поднять Ollama и модель

```bash
ollama serve
ollama pull qwen2.5-coder:1.5b
```

Рекомендуемые параметры для проверки:

- `num_ctx=4096`
- `num_predict=256`
- `batch=1`
- `parallel=1`

### 3. Запуск API

```bash
uvicorn app.main:app --reload --port 8080
```

UI будет доступен по адресу `http://localhost:8080/`.

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
