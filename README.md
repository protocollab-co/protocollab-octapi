# protocollab-octapi

Фаза 1 (Day 1): локальная генерация YAML-контракта для MWS Octapi через Ollama и валидация через компоненты protocollab.

## Что уже реализовано

- FastAPI backend с endpoint-ами:
	- `GET /health`
	- `POST /generate`
- Генерация YAML через локальную модель Ollama `qwen2.5-coder:1.5b`.
- Безопасный парсинг YAML через `yaml_serializer.SerializerSession`.
- Валидация контракта через `protocollab.jsonschema_validator`.
- Валидация `parameters.condition` для `array_filter` через `protocollab.expression.validate_expr`.
- Единый формат ошибки: `field`, `message`, `expected`, `got`, `hint`, `source`.
- Минимальный UI на одной странице (`/`) для демо потока.

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
	"model": "qwen2.5-coder:1.5b"
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
	"yaml": {
		"operation": "array_last",
		"parameters": {
			"source": "wf.vars.emails"
		}
	},
	"attempts": 1
}
```

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
