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
