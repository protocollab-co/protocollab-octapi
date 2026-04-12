# День 3. Шаблоны Lua и безопасное исполнение

## Цель дня
Перевести валидный YAML в исполняемый Lua через безопасный шаблонный слой и песочницу.

## Обязательные задачи
1. Создать 7 шаблонов Lua:
	- `array_last`
	- `math_increment`
	- `object_clean`
	- `array_filter`
	- `datetime_iso`
	- `datetime_unix`
	- `ensure_array_field`
2. Реализовать строгий `template selector` (`operation -> template`) с ошибкой на неизвестную операцию.
3. Встроить `to_lua(ast)` в генерацию `array_filter`.
4. Добавить синтаксическую проверку `luac -p`.
5. Подключить Docker sandbox с ограничениями: timeout 5s, memory 128MB, `--network none`.
6. Вернуть единый результат выполнения: `status`, `stdout`, `stderr`, `exit_code`.

## Интеграция protocollab (обязательно)
1. Для `array_filter` строить выражение через AST `protocollab.expression`.
2. Использовать `to_lua(ast)` как единственный путь трансляции `condition` в Lua.
3. Не допускать строковой подстановки `condition` в обход AST.

## Ограничения
1. Никакой генерации кода в обход шаблонов.
2. Никаких сетевых вызовов из sandbox.
3. Ошибки `luac` и sandbox должны быть пригодны для автоматического feedback в модель.

## Definition of Done
1. Для каждого из 7 шаблонов есть минимум 1 рабочий кейс.
2. На валидном YAML код проходит `luac` и выполняется в sandbox.
3. Ошибки selector/`luac`/sandbox возвращаются в API в контролируемом формате.
4. Переданы: каталог шаблонов, правила selector, контракт результата sandbox, стабильные E2E-кейсы.
5. Для `array_filter` подтверждён путь `protocollab.expression` → AST → `to_lua`.

## Статус реализации
1. Добавлен endpoint `POST /execute` с двумя режимами входа: `session_id` или inline `yaml`.
2. Реализован строгий selector `operation -> template` без fallback.
3. Добавлены 7 шаблонов в `templates/octapi`:
	- `array_last.lua.jinja2`
	- `math_increment.lua.jinja2`
	- `object_clean.lua.jinja2`
	- `array_filter.lua.jinja2`
	- `datetime_iso.lua.jinja2`
	- `datetime_unix.lua.jinja2`
	- `ensure_array_field.lua.jinja2`
4. Для `array_filter` используется только `parse_expr(condition) -> AST -> to_lua(ast)`.
5. Проверка `luac -p` запускается внутри Docker.
6. Sandbox исполнение использует ограничения:
	- timeout: 5s
	- memory: 128MB
	- network: `none`
7. Контракт результата sandbox унифицирован:
	- `status`
	- `stdout`
	- `stderr`
	- `exit_code`
8. При недоступном Docker возвращается контролируемая ошибка (`source = sandbox`), без падения API.

## Артефакты
1. Сервисы:
	- `app/services/template_selector.py`
	- `app/services/lua_codegen.py`
	- `app/services/lua_validator.py`
	- `app/services/sandbox_executor.py`
2. Интеграция API:
	- `app/main.py` (`/execute`, readiness в `/health`)
	- `app/models.py` (`ExecuteRequest`, `ExecuteResponse`, `ExecutionResult`)
	- `app/config.py` (sandbox/template settings)
3. Тесты:
	- `tests/test_day3_execute.py`
