# Library API

Спецификация OpenAPI 3.1 для сервиса «Библиотека» — управление книгами, читателями и выдачами.

## Структура репозитория

```
library-api/
├── openapi.yaml      # Основная спецификация OpenAPI 3.1
├── STYLE.md          # 10 правил проектирования API
├── REVIEW.md         # Саморевью по чек-листу (слайды 29–32)
├── README.md         # Этот файл
└── mock/             # Дополнительно: mock-сервер и примеры curl
    ├── server.py     # Простой mock-сервер на Python
    └── curl-examples.sh  # Примеры запросов через curl
```

## Ресурсы

| Ресурс | Поля | Описание |
|---|---|---|
| **Book** | id, title, author, isbn, published_year, total_copies, available_copies (readOnly) | Книга в библиотеке |
| **Reader** | id, full_name, email, registered_at | Читатель |
| **Loan** | id, book_id, reader_id, loaned_at, due_date, returned_at (nullable) | Выдача книги |

## Бизнес-правила

1. Выдача только при `available_copies > 0`.
2. Не более 5 активных выдач на читателя (`returned_at == null`).
3. Возврат: `POST /loans/{id}/return`, не DELETE.
4. Просроченные: `GET /loans?status=overdue`.
5. Нельзя удалить книгу или читателя с активными выдачами.
6. `due_date` новой выдачи должна быть позже текущей даты.
7. `available_copies` вычисляет сервер; клиент не передаёт это поле.

## Быстрый старт

### 1. Просмотр спецификации

Откройте `library-api/openapi.yaml` в любом редакторе или загрузите на
[Swagger Editor](https://editor.swagger.io/) для визуального просмотра.

### 2. Запуск mock-сервера

```bash
cd library-api/mock
python server.py
```

Сервер будет доступен на `http://localhost:8080`.

### 3. Примеры запросов через curl

См. файл `mock/curl-examples.sh`.

Краткий обзор:

```bash
# Список книг
curl "http://localhost:8080/v1/books?page=1&limit=10&sort=title"

# Создание книги
curl -X POST "http://localhost:8080/v1/books" \
  -H "Content-Type: application/json" \
  -d '{"title":"1984","author":"Джордж Оруэлл","isbn":"978-5-17-999999-9","published_year":1949,"total_copies":4}'

# Создание выдачи с идемпотентностью
curl -X POST "http://localhost:8080/v1/loans" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"book_id":1,"reader_id":1,"due_date":"2024-11-01T09:00:00Z"}'

# Возврат книги
curl -X POST "http://localhost:8080/v1/loans/201/return"

# Просроченные выдачи
curl "http://localhost:8080/v1/loans?status=overdue"
```

## Дополнительное задание

Выполнены все четыре пункта:

1. **Mock-сервер + curl** — см. каталог `mock/`.
2. **Bearer JWT** — схема `securitySchemes` описана в `openapi.yaml` (компонент `BearerAuth`).
3. **Устаревшее поле** — поле `published_year` в схеме `Book` помечено `deprecated: true`.
4. **Таблица изменений v2** — см. приложение в `REVIEW.md`.

## Авторизация

API поддерживает авторизацию через Bearer JWT. Добавьте заголовок:

```
Authorization: Bearer <JWT_TOKEN>
```

Схема описана в `components/securitySchemes` и применяется ко всем операциям через глобальный `security`.

## Лицензия

MIT
