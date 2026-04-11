# День 2. ReAct-цикл и диалог уточнений

## Цель дня
Сделать управляемый цикл уточнения и исправления YAML с ограничением по попыткам.

## Обязательные задачи
1. Ввести `session state`: `attempts`, `original_prompt`, `context`, `history`, `yaml`.
2. Реализовать ReAct-цикл: генерация → валидация → structured feedback → повтор (до 3 попыток).
3. Добавить endpoint `/ask` для пользовательских уточнений.
4. После ответа пользователя обновлять контекст и перезапускать генерацию.
5. Нормализовать feedback для модели: `field`, `message`, `expected`, `got`, `hint`.

## Интеграция protocollab (обязательно)
1. В каждом цикле валидации использовать связку: `yaml_serializer` → `jsonschema_validator`.
2. Для операций с `condition` повторно запускать `protocollab.expression` после каждого исправления YAML.
3. Формировать structured feedback на основе ошибок валидаторов `protocollab`.

## Ограничения
1. Максимум 3 итерации на сессию.
2. После исчерпания лимита возвращать контролируемую ошибку.
3. Не расширять scope за пределы диалога и валидации.

## Definition of Done
1. Минимум 2 кейса исправляются в пределах 3 попыток.
2. Минимум 1 кейс проходит через `/ask` и завершается корректным YAML.
3. В логах есть трассировка по каждой попытке.
4. Переданы: контракт сессии, примеры structured feedback, финальный YAML для template selector.
5. В feedback явно отражается источник ошибки (`schema`/`expression`).

## Реализованный контракт сессии
- `session_id`: строковый идентификатор сессии.
- `attempts`: текущее число выполненных попыток.
- `max_attempts`: лимит попыток (3).
- `original_prompt`: исходный пользовательский запрос.
- `context`: накопленный контекст с уточнениями.
- `history`: список попыток с `attempt`, `prompt`, `yaml`, `feedback`.
- `yaml`: последний валидный YAML (если достигнут).

## Structured feedback (примеры)
### Пример 1: schema
```json
{
	"field": "operation",
	"message": "'unknown' is not one of ['array_filter', 'array_last', 'math_increment', 'object_clean', 'datetime_iso', 'datetime_unix', 'ensure_array_field']",
	"expected": "schema rule properties.operation.enum",
	"got": "unknown",
	"hint": "Check required fields, operation-specific parameters, and data types.",
	"source": "schema"
}
```

### Пример 2: expression
```json
{
	"field": "parameters.condition",
	"message": "Invalid condition expression: duplicated operator",
	"expected": "valid protocollab expression",
	"got": "item.Discount ~= ~= nil",
	"hint": "Use operators supported by protocollab.expression.",
	"source": "expression"
}
```

## Финальный YAML для template selector
```yaml
operation: template_selector
parameters:
	source: wf.vars.templates
	condition: item.type == "invoice"
	template: "invoice_v2"
```
