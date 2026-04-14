# Ubuntu Runbook: protocollab-octapi

Подробная инструкция для запуска проекта на Ubuntu (рекомендуемо: Ubuntu 22.04/24.04 LTS).

## 1. Что будет в итоге

После выполнения инструкции вы получите:
- API на `http://localhost:8000`
- Ollama на `http://localhost:11434`
- Web UI на `http://localhost:8000/`
- Рабочие эндпоинты: `/health`, `/generate`, `/ask`, `/execute`

---

## 2. Варианты запуска

Есть 2 поддерживаемых сценария:

1. `Docker` (рекомендуется для воспроизводимости)
2. `Без Docker` (быстрее старт, но `/execute` всё равно использует Docker sandbox)

---

## 3. Предварительные требования

## 3.1 Системные пакеты

```bash
sudo apt update
sudo apt install -y git curl ca-certificates jq python3 python3-venv python3-pip
```

## 3.2 Клонирование проекта

```bash
git clone https://github.com/protocollab-co/protocollab-octapi.git
cd protocollab-octapi
git submodule update --init --recursive
```

---

## 4. Запуск через Docker (рекомендуется)

## 4.1 Установка Docker Engine + Compose Plugin

Если Docker ещё не установлен:

```bash
sudo apt remove -y docker docker-engine docker.io containerd runc || true

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
newgrp docker
```

Проверка:

```bash
docker --version
docker compose version
docker info >/dev/null && echo "docker ok"
```

## 4.2 Запуск стека

```bash
docker compose up -d --build
docker compose ps
```

Ожидаемо: сервисы `ollama` и `api` в статусе `Up`.

## 4.3 Проверка здоровья

```bash
curl -sS http://localhost:8000/health | jq .
```

Ожидаемо минимум:
- `status`: `ok` или `degraded`
- `ollama`: `available` (после загрузки модели)

## 4.4 Если модель отсутствует

По умолчанию используется `qwen2.5-coder:1.5b`.
Проверьте модели:

```bash
curl -sS http://localhost:11434/api/tags | jq .
```

Если нужной модели нет, загрузите её:

```bash
docker exec -it localscript-ollama ollama pull qwen2.5-coder:1.5b
```

---

## 5. Запуск без Docker Compose

Этот режим полезен для отладки API и генерации.

Важно: `/execute` по архитектуре проекта использует Docker sandbox (`docker run lua:5.4...`), поэтому Docker Engine всё равно нужен для полного e2e.

## 5.1 Ollama на хосте

Установка Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Запуск сервера (в отдельном терминале):

```bash
ollama serve
```

Загрузка модели:

```bash
ollama pull qwen2.5-coder:1.5b
```

## 5.2 API на хосте

В другом терминале:

```bash
cd ~/protocollab-octapi
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

export PYTHONPATH=.
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5-coder:1.5b

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Проверка:

```bash
curl -sS http://localhost:8000/health | jq .
```

---

## 6. Smoke-тест API (обязательно)

## 6.1 Generate

```bash
curl -sS -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Get last email from the list"}' | jq .
```

Ожидаемо:
- `is_complete: true`
- `yaml.operation: array_last`

## 6.2 Ask (пример диалога)

```bash
curl -sS -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Увеличь значение переменной на 3"}' | jq .
```

Если вернулось `is_complete: false`, отправьте уточнение:

```bash
curl -sS -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SESSION_ID>","answer":"переменная называется wf.vars.counter"}' | jq .
```

## 6.3 Execute

```bash
curl -sS -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "yaml": {"operation":"array_last","parameters":{"source":"wf.vars.emails"}},
    "context": {"wf": {"vars": {"emails": ["a@example.com", "b@example.com", "c@example.com"]}}}
  }' | jq .
```

Ожидаемо:
- `execution_result.status: success`
- `stdout` содержит `c@example.com`

---

## 7. Запуск тестов на Ubuntu

## 7.1 Быстрый локальный прогон

```bash
pytest tests/ -q -m "not integration"
```

## 7.2 Полный прогон

```bash
pytest tests/ -q
```

## 7.3 Integration suite (8 examples)

```bash
pytest tests/test_all_samples.py -q
```

Если API/Ollama не подняты, integration-тесты корректно `skip`.

---

## 8. Troubleshooting

## 8.1 `address already in use` (порт 8000 или 11434)

Проверка:

```bash
ss -ltnp | grep -E ':8000|:11434'
```

Остановить конфликтующий процесс/контейнер и повторить запуск.

## 8.2 `/health` возвращает `model_not_found`

Значит модель не загружена. Выполните:

```bash
ollama pull qwen2.5-coder:1.5b
```

(или внутри контейнера: `docker exec -it localscript-ollama ollama pull qwen2.5-coder:1.5b`)

## 8.3 `/execute` падает с ошибкой sandbox

Проверьте Docker доступ:

```bash
docker info >/dev/null && echo ok
```

Проверьте, что образ `lua:5.4` доступен:

```bash
docker pull lua:5.4
```

## 8.4 Проблемы с DNS между контейнерами

```bash
docker compose down
docker network prune -f
docker compose up -d --build
```

## 8.5 Чистый рестарт окружения

```bash
docker compose down -v
docker system prune -f
docker compose up -d --build
```

---

## 9. Команды остановки

Docker режим:

```bash
docker compose down
```

Host режим:
- остановить `uvicorn` (`Ctrl+C`)
- остановить `ollama serve` (`Ctrl+C`)

---

## 10. Рекомендуемый порядок для защиты

1. `docker compose up -d --build`
2. `curl /health`
3. `POST /generate`
4. `POST /ask` (опционально, диалог)
5. `POST /execute`
6. показать UI `http://localhost:8000/`
7. `pytest tests/test_all_samples.py -q` (если время позволяет)
