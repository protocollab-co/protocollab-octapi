# Documentation Structure

Документация проекта организована по категориям для удобства навигации.

## 📋 Структура папок

### `boost/` — UI/UX Улучшения ✨
Документация по улучшению интерфейса демонстрации:
- **ui.md** — План и выполнение UI enhancement (8 примеров, syntax highlighting, история, grid layout)

### `verification/` — Верификация и тестирование
Документы для финальной проверки соответствия требованиям Day 5:
- **offline_verification.md** — Доказательство работы в offline режиме (0 внешних API)
- **reference_scenario.md** — Эталонный тестовый сценарий с curl командами
- **vram_measurement.md** — Методология измерения потребления памяти
- **day5_delivery_checklist.md** — Чеклист сдачи проекта (Definition of Done)

### `deliverables/` — Итоговые артефакты
Готовые материалы для предоставления жюри:
- **presentation_outline.md** — Сценарий 7-минутной защиты проекта
- **demo_video.md** — План и спецификация демо-видео
- **protocollab_integration.md** — Подробная документация интеграции protocollab

### `planning/` — Планирование и подготовка
Планы работ и задачи:
- **plan_hackathon.md** — План выполнения хакатона
- **plan_protocollab_octapi.md** — План реализации Day 5 проекта
- **task_hackathon.md** — Детальные задачи для хакатона

### `days/` — Дневные логи
История развития по дням:
- **day1.md** — День 1: Инициализация
- **day2.md** — День 2: Основная разработка
- **day3.md** — День 3: Интеграция
- **day4.md** — День 4: Оптимизация
- **day5.md** — День 5: Финальная верификация

### `diagrams/` — Визуальной архитектуры
Диаграммы в формате Mermaid:
- **comprehensive_v1.mmd** — Полная архитектурная диаграмма
- **day5_architecture.mmd** — C4-диаграмма финальной архитектуры
- **mvp_day1_day4_flow.mmd** — MVP-диаграмма потока обработки

### `roadmap/` — Дорожные карты
Стратегические планы развития:
- **roadmap_hackathon.md** — Дорожная карта хакатона
- **roadmap_enterprise.md** — Планы промышленного использования

## 🎯 Рекомендации для навигации

**Для жюри:**
1. Начните с `deliverables/presentation_outline.md`
2. Посмотрите `deliverables/demo_video.md`
3. Проверьте `verification/offline_verification.md`
4. Изучите `deliverables/protocollab_integration.md`

**Для разработчиков:**
1. `planning/plan_protocollab_octapi.md` — общее описание
2. `days/day5.md` — текущий прогресс
3. `verification/reference_scenario.md` — как протестировать
4. `diagrams/` — архитектуру и взаимодействие компонентов

**Для архитекторов:**
1. `diagrams/day5_architecture.mmd`
2. `diagrams/comprehensive_v1.mmd`
3. `deliverables/protocollab_integration.md`
