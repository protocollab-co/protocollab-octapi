## Обновлённый детализированный план хакатона (с интеграцией MWS Octapi и `protocollab`)

**Целевой результат:** за 5 дней собрать воспроизводимый MVP, где пользователь вводит задачу на русском или английском, система локально через Ollama получает YAML-метаданные (спецификацию операции для MWS Octapi), валидирует их с использованием компонентов `protocollab`, при необходимости делает до 3 итераций уточнения, затем генерирует безопасный Lua-код по шаблону (с трансляцией условий через `protocollab.expression`), прогоняет `luac` и Docker‑sandbox и отдаёт результат.  
**Основание:** `task_hackathon.md`, `roadmap_hackathon.md`, публичная выборка `sample_requests.md` (8 кейсов MWS Octapi), `protocollab` как инфраструктурный фундамент.

---

## 1. Границы MVP (жестко)

- **Входит в MVP:**
  - Локальная LLM `qwen2.5-coder:1.5b` (Ollama)
  - FastAPI (бэкенд)
  - YAML‑контракт для MWS Octapi (operation + parameters)
  - Валидация через `jsonschema_validator` (из `protocollab`)
  - Безопасная загрузка YAML через `yaml_serializer` (из `protocollab`)
  - Проверка выражений (`condition`) через `protocollab.expression` (лексер, парсер, валидатор, evaluator)
  - Функция `to_lua(ast)` для трансляции AST в строку Lua
  - ReAct‑цикл (до 3 итераций) со структурированным фидбеком
  - Диалоговое уточнение (endpoint `/ask`)
  - **7 шаблонов Lua** (под 8 кейсов `sample_requests.md`):  
    `array_last`, `math_increment`, `object_clean`, `array_filter`, `datetime_iso`, `datetime_unix`, `ensure_array_field`
  - Template selector (строгий маппинг operation → шаблон)
  - `luac -p` (синтаксическая проверка)
  - Docker‑sandbox с моками `wf.vars`, `wf.initVariables`, `_utils.array`
  - Минимальный UI (одна страница)
  - `docker-compose.yml` и однокомандный запуск
  - Расширенный README, C4‑диаграмма, демо‑видео, презентация

- **Исключается полностью:**  
  Cache, RAG, DAG orchestration, audit, metrics, oracle storage, version storage, генерация парсеров бинарных протоколов (`protocollab.generators`), любые необязательные подсистемы.  
  Также исключаются шаблоны `file_ops`, `http_request`, `json_parse` – они не соответствуют MWS Octapi.

---

## 2. Целевой pipeline (обновлённый)

```mermaid
flowchart LR
    User[Пользовательский запрос] --> API[FastAPI: /generate]
    API --> Ollama[Ollama: qwen2.5-coder:1.5b]
    Ollama --> YAML[YAML-метаданные<br>operation + parameters]
    YAML --> SafeLoad[yaml_serializer.load_yaml]
    SafeLoad --> SchemaValidate[jsonschema_validator]
    SchemaValidate -- ошибка --> Feedback[structured feedback]
    Feedback --> Ollama
    SchemaValidate -- OK --> ExprValidate[protocollab.expression<br>validate condition]
    ExprValidate -- ошибка --> Feedback
    ExprValidate -- OK --> TemplateSelector[Template selector]
    TemplateSelector --> Jinja[Jinja2 + to_lua(ast)]
    Jinja --> LuaCode[Lua-код]
    LuaCode --> Luac[luac -p]
    Luac -- ошибка --> Feedback
    Luac -- OK --> Sandbox[Docker sandbox<br>моки wf.vars, _utils]
    Sandbox --> Response[Ответ пользователю]
```

**Примечание:** Для операций без `condition` (например, `array_last`, `math_increment`) этап `ExprValidate` пропускается.

---

## 3. API и внутренние контракты

### Публичные сценарии
1. `GET /health` – проверка живости сервиса (включая доступность Ollama и модели).
2. `POST /generate` – основной эндпоинт:  
   *Запрос:* `{"prompt": "текст задачи", "context": {"wf": {"vars": {...}}}}` (опционально)  
   *Ответ:* `{"code": "lua{...}lua", "yaml": {...}, "attempts": 1}`
3. `POST /ask` – диалоговое уточнение:  
   *Запрос:* `{"session_id": "...", "answer": "пользовательский ответ"}`  
   *Ответ:* либо новый YAML, либо уточняющий вопрос.

### Внутренние контракты

**YAML-структура (схема `mws_operation.schema.json`):**
```yaml
operation: array_filter   # одно из: array_last, math_increment, object_clean, array_filter, datetime_iso, datetime_unix, ensure_array_field
parameters:
  source: "wf.vars.parsedCsv"          # для array_filter, array_last, object_clean
  condition: "item.Discount ~= nil"    # только для array_filter
  step: 1                              # для math_increment
  fields_to_remove: ["ID", "CALL"]     # для object_clean
  date_field: "wf.vars...DATUM"        # для datetime_iso
  time_field: "wf.vars...TIME"         # для datetime_iso
  # и т.д.
```

**Единый формат ошибки валидации** (из `jsonschema_validator` + наши дополнения):
```json
{
  "field": "parameters.source",
  "message": "'source' is a required property",
  "expected": "string",
  "got": "missing",
  "hint": "For array_filter you must provide source (e.g., wf.vars.data)"
}
```

**Формат результата sandbox:**
```json
{
  "status": "success" | "error",
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0
}
```

---

## 4. Backend-каркас (компоненты)

- HTTP‑слой на FastAPI
- Клиент для Ollama (`httpx`)
- Сервис безопасной загрузки YAML (`yaml_serializer.SafeLoader`)
- Сервис валидации JSON Schema (`jsonschema_validator.ValidatorFactory`)
- Сервис проверки выражений (`protocollab.expression.validator`)
- Сервис трансляции AST → Lua (`to_lua` – наша реализация)
- Session state (in‑memory dict: `session_id → {attempts, context, history, yaml}`)
- Template selector (словарь `operation → jinja2_template`)
- Генератор Lua (Jinja2 + `to_lua` фильтр)
- Сервис запуска `luac` (subprocess)
- Сервис запуска Docker‑sandbox (docker‑sdk или subprocess)

**Definition of done для этапа 4:** сервис стартует, `/health` отвечает 200, ошибки возвращаются в едином формате.

---

## 5. Контракт YAML и валидация (с `protocollab`)

1. **JSON Schema** – создаём файл `mws_operation.schema.json` со списком допустимых `operation` и шаблонами параметров для каждой операции (можно упрощённо, без `allOf`, а специфику проверять в коде).
2. **Загрузка YAML** – через `yaml_serializer.load_yaml` с ограничениями: `max_size=10_000`, `max_depth=10`, запрет `!include`.
3. **Валидация схемы** – `jsonschema_validator` с backend `auto` (предпочтёт `jsonscreamer`, если установлен). При ошибке формируем структурированный фидбек (поле, сообщение, ожидание).
4. **Дополнительная валидация для `array_filter`** – вызываем `validate_expr(condition)` из `protocollab.expression`. Если ошибка – возвращаем позицию и сообщение.
5. **Количество повторов** – максимум 3 попытки генерации YAML (учитывая фидбек). При 3 неудачах – контролируемая ошибка.

**Definition of done:** На типовых примерах (№1,2,6 из выборки) модель выдаёт валидный YAML с первого или второго раза, либо корректно запрашивает уточнение.

---

## 6. ReAct‑цикл и диалог

- **Логика:**
  1. При первом запросе – отправляем модели промпт с инструкцией сгенерировать YAML.
  2. Если валидация не прошла – формируем структурированный фидбек (поля `field`, `message`, `expected`, `got`, `hint`) и отправляем модели повторно (увеличиваем `attempts`).
  3. Если проблема в недостатке данных (модель явно указала, что не знает имя переменной или структуру) – вместо повторной генерации задаём пользователю вопрос через `/ask`.
  4. После ответа пользователя обновляем контекст сессии (добавляем информацию) и повторяем генерацию.
  5. После 3 неудач – завершаем с ошибкой.

- **Session state** хранит: `attempts`, `original_prompt`, `context` (из запроса и ответов), `history` (предыдущие YAML и ошибки).

**Definition of done:** Реализован endpoint `/ask`, есть сценарий, где модель задаёт вопрос и после ответа генерирует корректный YAML.

---

## 7. Шаблонный слой Lua (7 шаблонов для MWS Octapi)

Создаём папку `templates/` с файлами:

| Файл шаблона | Operation | Генерация (пример) |
|--------------|-----------|--------------------|
| `array_last.lua` | `array_last` | `return {{ source }}[#{{ source }}]` |
| `math_increment.lua` | `math_increment` | `return {{ variable }} + {{ step }}` |
| `object_clean.lua` | `object_clean` | Обход массива, удаление `fields_to_remove` |
| `array_filter.lua` | `array_filter` | Фильтрация с условием `{{ condition_ast | to_lua }}` |
| `datetime_iso.lua` | `datetime_iso` | Извлечение `date_field`, `time_field`, форматирование в ISO |
| `datetime_unix.lua` | `datetime_unix` | Парсинг ISO → Unix timestamp (включая миллисекунды, offset) |
| `ensure_array_field.lua` | `ensure_array_field` | Рекурсивное приведение поля `items` к массиву |

**Template selector** – простой `dict`:
```python
TEMPLATE_MAP = {
    "array_last": "array_last.lua",
    "math_increment": "math_increment.lua",
    "object_clean": "object_clean.lua",
    "array_filter": "array_filter.lua",
    "datetime_iso": "datetime_iso.lua",
    "datetime_unix": "datetime_unix.lua",
    "ensure_array_field": "ensure_array_field.lua",
}
```

**Важно:** Для `array_filter` условие передаётся в шаблон как AST, а в Jinja2 используется фильтр `to_lua`, который мы реализуем отдельно.

**Definition of done:** Каждый из 7 шаблонов сгенерирован и протестирован на соответствующем примере из `sample_requests.md` (хотя бы один запуск в sandbox).

---

## 8. Проверки кода и sandbox

1. **`luac -p`** – синтаксическая проверка. При ошибке возвращаем фидбек модели (строка ошибки, номер строки).
2. **Docker‑sandbox**:
   - Базовый образ: `alpine:latest` + `lua5.4` (или `lua5.3`).
   - При запуске подставляем моки:  
     ```lua
     wf = { vars = <context.wf.vars or {}>, initVariables = <context.wf.initVariables or {}> }
     _utils = { array = { new = function() return {} end, markAsArray = function(t) return t end } }
     -- код пользователя
     ```
   - Ограничения: `timeout 5s`, `memory 128MB`, `--network none`.
   - Захват `stdout`, `stderr`, код возврата.
3. **Возврат результата** в едином формате.

**Definition of done:** Sandbox успешно выполняет хотя бы один корректный Lua-скрипт и возвращает результат, а также корректно обрабатывает ошибки (таймаут, память, синтаксис).

---

## 9. Минимальный UI

Одна HTML-страница (можно встроить в FastAPI через `templates` или отдельный статический файл). Компоненты:
- Поле ввода задачи (`textarea`)
- Кнопка «Сгенерировать»
- Блок отображения YAML (или ошибки валидации)
- Блок уточняющего вопроса (если есть) и поле для ответа
- Блок сгенерированного Lua-кода (с подсветкой)
- Кнопка «Запустить в песочнице»
- Блок вывода sandbox (stdout/stderr)

Приоритет – работающий demo path, а не дизайн.

---

## 10. Упаковка запуска (одна команда)

- **`docker-compose.yml`** включает:
  - `ollama` сервис (с предзагруженной моделью или командой `ollama pull`)
  - `backend` (FastAPI + зависимости)
  - (опционально) `redis` для сессий, но для MVP можно in‑memory
- **Инструкция в README:**
  ```bash
  docker-compose up --build
  # в другом терминале:
  docker exec -it ollama ollama pull qwen2.5-coder:1.5b
  ```
- **Параметры запуска Ollama** (прописаны в `docker-compose.override.yml` или в команде):  
  `num_ctx 4096, num_predict 256, batch 1, parallel 1`
- **Отсутствие внешних AI API** – проверяем, что нет вызовов к OpenAI и т.п.

---

## 11. README (расширенный)

Содержит:
- Что делает проект (генерация Lua для MWS Octapi)
- Какие ограничения хакатона закрывает (локальность, VRAM, приватность)
- Как скачать модель: `ollama pull qwen2.5-coder:1.5b`
- Как поднять одной командой: `docker-compose up --build`
- Как проверить работу: `curl -X POST http://localhost:8080/generate -H "Content-Type: application/json" -d '{"prompt":"...","context":{...}}'`
- Ограничения MVP (только 7 операций, без сети в sandbox, простой UI)
- Демонстрационный сценарий (например, «последний элемент массива»)
- Как измерить VRAM: запустить `nvidia-smi` в момент генерации, команда в README
- Благодарность `protocollab` с указанием использованных компонентов

---

## 12. Архитектурная диаграмма (C4 для MVP)

Создаём отдельный файл `mvp_diagram.mmd` (Mermaid). Уровень контейнеров:
- Пользователь → Веб-UI → Backend (FastAPI)
- Backend → Ollama (модель)
- Backend → `protocollab` (yaml_serializer, jsonschema_validator, expression)
- Backend → Template Engine (Jinja2 + to_lua)
- Backend → `luac` (подпроцесс)
- Backend → Docker sandbox

Уровень компонентов внутри Backend (можно упростить).

---

## 13. Тестовый контур

- **Позитивные сценарии:** 8 примеров из `sample_requests.md` (каждый как отдельный тест).
- **Негативные:**
  - Невалидный YAML (отсутствует `operation`)
  - Неизвестный `operation`
  - Ошибка в `condition` (синтаксис)
  - Исчерпание 3 попыток
  - Падение sandbox (бесконечный цикл, переполнение памяти)
- **Проверка шаблонов:** каждый из 7 шаблонов хотя бы на одном кейсе.

Тесты реализовать через `pytest` (интеграционные, с запуском реальной модели – можно использовать заглушку для CI, но на демо – живые).

---

## 14. Финальные артефакты

1. Открытый репозиторий (GitHub) с кодом
2. README (расширенный)
3. `docker-compose.yml` + инструкция
4. C4-диаграмма (MVP) в формате Mermaid
5. Демо-видео (2–3 минуты, проход по одному сценарию)
6. Презентация (7 минут, акцент на архитектуре, безопасности, использовании `protocollab`)
7. Зафиксированный сценарий эталонного запроса (например, «Отфильтруй массив по Discount»)
8. Подтверждение параметров модели и VRAM (скриншот `nvidia-smi`)

---

## Разбивка по дням (с учётом `protocollab`)

### День 0 (вечер 10.04) – Старт и инфраструктура
- Создать репозиторий, `docker-compose.yml` (FastAPI, Ollama, Redis опционально)
- Установить `protocollab` из git, проверить работу `yaml_serializer`, `jsonschema_validator` на тестовых YAML
- **ML:** скачать `qwen2.5-coder:1.5b`, убедиться, что Ollama отвечает
- **Бэк:** FastAPI skeleton, endpoint `/health`, базовый клиент Ollama
- **Фулстэк:** простая HTML-страница

### День 1 (11.04) – YAML-контракт, валидация, прокачка `expression`
- **ML:** написать промпт для генерации YAML (operation + parameters) с few-shot (3 примера)
- **Бэк:** 
  - Создать `mws_operation.schema.json`
  - Реализовать `/generate`: вызов Ollama → `yaml_serializer.load_yaml` → `jsonschema_validator.validate` → структурированный фидбек при ошибке
  - Для `array_filter` добавить `validate_expr(condition)`
- **Прокачка `expression`:**
  - Добавить в лексер/парсер оператор `#` (длина массива)
  - Добавить `~=` как синоним `!=`
  - Реализовать функцию `to_lua(ast)` (поддержка `Name`, `Attribute`, `Subscript`, `BinOp` для `+ - * / == ~= and or`, `Literal`, `UnaryOp` для `not -`)
- **Фулстэк:** UI выводит YAML и ошибки

**DoD:** Для запросов «последний элемент массива» и «инкремент» модель выдаёт валидный YAML, и система возвращает успех.

### День 2 (12.04) – ReAct-цикл, диалог, session state
- **ML:** промпт для исправления ошибок (вход – структурированный фидбек)
- **Бэк:**
  - In‑memory хранилище сессий (`dict`)
  - Цикл до 3 попыток: при ошибке → фидбек → повторный вызов модели
  - Endpoint `/ask` – принимает ответ пользователя, обновляет контекст, повторяет генерацию
- **Фулстэк:** UI показывает счётчик попыток, поле для ответа на уточнение

**DoD:** Сценарий, где модель запрашивает имя переменной, и после ответа пользователя генерирует корректный YAML.

### День 3 (13.04) – Шаблоны Lua, `luac`, sandbox, `to_lua` в действии
- **Бэк:**
  - Создать 7 Jinja2-шаблонов (см. таблицу)
  - Template selector
  - В генерацию для `array_filter` встроить `to_lua(ast)`
  - Добавить проверку `luac -p`
  - Написать Dockerfile для sandbox (Lua + моки), добавить скрипт запуска с ограничениями (Python + docker‑sdk)
- **Фулстэк:** UI показывает Lua-код, кнопка «Запустить», вывод sandbox

**DoD:** Полный end‑to‑end для `array_filter` (например, запрос «отфильтруй массив по Discount» → генерация → `luac` → sandbox → вывод результата).

### День 4 (14.04) – Интеграция, тестирование, документация
- **Все:** прогнать все 8 примеров из `sample_requests.md` (регрессия)
- **Бэк:** дописать `to_lua` для оставшихся узлов (Ternary, если нужно), добавить логирование
- **Тесты:** написать `pytest` интеграционные тесты (можно с реальной моделью, но с кэшированием)
- **Документация:** 
  - README (инструкция, примеры, описание схемы)
  - C4-диаграмма в `mvp_diagram.mmd`
  - Запись демо-видео
  - Подготовка презентации (7 слайдов)
- **Фулстэк:** финальная полировка UI

### День 5 (утро 15.04) – Финальное тестирование и сдача
- **Все:** 
  - Прогнать эталонный запрос (выбрать один из примеров, например №6)
  - Замерить VRAM через `nvidia-smi` (peak) при `num_ctx=4096, num_predict=256`
  - Проверить `docker-compose up --build` на чистом сервере (или локальной машине без предварительных зависимостей)
- **Пуш** финальной версии, тег `v1.0-hackathon`
- **Сдача** до 12:00 по московскому времени

---

## Главные риски и mitigation (обновлённые)

| Риск | Решение |
|------|---------|
| Модель генерирует нестабильный YAML (пропускает поля, пишет лишнее) | Жёсткий output contract в промпте + пост‑процессинг (извлечение YAML из маркдауна). При повторных ошибках – переключение на упрощённую схему. |
| `to_lua` не успеваем реализовать для всех узлов | Сделать минимальную версию (поддержка только нужных для `array_filter` операций). Остальное – строковая вставка (менее безопасно, но работает). |
| 7 шаблонов – большой объём | Распределить: backend‑разработчик пишет шаблоны, ML‑инженер – промпты и `to_lua`, фулстэк – UI и интеграцию. Начать с 3 шаблонов (array_filter, math_increment, array_last), остальные сделать в день 3–4. |
| `protocollab.expression` не поддерживает `#` и `~=` | Мы уже запланировали доработку в день 1. Патчить локально в своём форке. |
| Docker‑sandbox не запускается на машине жюри (нет Docker) | В README указать, что Docker обязателен. Альтернатива – запуск через `lua` напрямую с изоляцией через `setrlimit`, но это сложнее. Оставляем Docker. |
| Выход за VRAM (пик >8GB) | Использовать `qwen2.5-coder:1.5b` (1–2 GB), при необходимости – квантизированную 7B (Q4 ~5GB). В README указать точный тег и параметры. |

---

## Критерий успеха

План считается выполненным, если жюри может:
1. Выполнить `docker-compose up --build`
2. Отправить POST‑запрос на `/generate` с русскоязычным запросом (например, «Отфильтруй массив, оставив только элементы с Discount не пустым»)
3. Получить валидный Lua‑код, который после запуска в песочнице (кнопка в UI или curl) возвращает ожидаемый отфильтрованный массив.
4. Подтвердить, что пиковое использование VRAM не превышает 8 GB (скриншот `nvidia-smi`).
5. Убедиться, что ни один запрос не уходит во внешние AI‑сервисы (можно проверить логи).

---

**План утверждён. Команда готова к старту. Удачи на хакатоне!**