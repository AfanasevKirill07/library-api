#!/bin/bash
# Примеры запросов к Library API через curl
# Mock-сервер должен быть запущен: python mock/server.py

BASE="http://localhost:8080/v1"
CONTENT="-H 'Content-Type: application/json'"

echo "=== 1. Список книг (с пагинацией и сортировкой) ==="
curl -s "$BASE/books?page=1&limit=5&sort=title" | python3 -m json.tool
echo

echo "=== 2. Создать книгу ==="
curl -s -X POST "$BASE/books" $CONTENT \
  -d '{"title":"1984","author":"Джордж Оруэлл","isbn":"978-5-17-999999-9","published_year":1949,"total_copies":4}' | python3 -m json.tool
echo

echo "=== 3. Получить книгу по ID ==="
curl -s "$BASE/books/1" | python3 -m json.tool
echo

echo "=== 4. Обновить книгу ==="
curl -s -X PUT "$BASE/books/1" $CONTENT \
  -d '{"title":"Война и мир (иллюстрированное издание)","total_copies":7}' | python3 -m json.tool
echo

echo "=== 5. Список читателей ==="
curl -s "$BASE/readers?page=1&limit=10" | python3 -m json.tool
echo

echo "=== 6. Создать читателя ==="
curl -s -X POST "$BASE/readers" $CONTENT \
  -d '{"full_name":"Алексей Сидоров","email":"alexey@example.com"}' | python3 -m json.tool
echo

echo "=== 7. Создать выдачу (с идемпотентностью) ==="
curl -s -X POST "$BASE/loans" $CONTENT \
  -H 'Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{"book_id":1,"reader_id":1,"due_date":"2024-11-01T09:00:00Z"}' | python3 -m json.tool
echo

echo "=== 8. Повторный запрос с тем же Idempotency-Key (ре플эй ответа) ==="
curl -s -X POST "$BASE/loans" $CONTENT \
  -H 'Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{"book_id":1,"reader_id":1,"due_date":"2024-11-01T09:00:00Z"}' | python3 -m json.tool
echo

echo "=== 9. Получить выдачу по ID ==="
curl -s "$BASE/loans/101" | python3 -m json.tool
echo

echo "=== 10. Вернуть книгу (POST /loans/{id}/return) ==="
curl -s -X POST "$BASE/loans/101/return" | python3 -m json.tool
echo

echo "=== 11. Просроченные выдачи ==="
curl -s "$BASE/loans?status=overdue" | python3 -m json.tool
echo

echo "=== 12. Ошибка: неверный JSON ==="
curl -s -X POST "$BASE/books" $CONTENT -d 'not-json' | python3 -m json.tool
echo

echo "=== 13. Удалить книгу (204, если нет активных выдач) ==="
curl -s -o /dev/null -w "Status: %{http_code}\n" -X DELETE "$BASE/books/999"
echo

echo "=== 14. Заголовок авторизации Bearer JWT ==="
curl -s -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." "$BASE/books/1" | python3 -m json.tool