#!/usr/bin/env python3
"""
Простой mock-сервер для Library API.
Реализует основные эндпоинты из openapi.yaml для демонстрации.

Запуск:
    python server.py

Сервер будет доступен на http://localhost:8080/v1/...
"""

import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# --- In-memory storage ---
books = {}
readers = {}
loans = {}
idempotency_store = {}  # key -> (request_body_hash, response, timestamp)

# --- Seed data ---
books[1] = {
    "id": 1, "title": "Война и мир", "author": "Лев Толстой",
    "isbn": "978-5-17-123456-7", "published_year": 1869,
    "total_copies": 5, "available_copies": 5,
}
books[2] = {
    "id": 2, "title": "Преступление и наказание", "author": "Фёдор Достоевский",
    "isbn": "978-5-17-765432-1", "published_year": 1866,
    "total_copies": 3, "available_copies": 3,
}

readers[1] = {
    "id": 1, "full_name": "Иван Иванов", "email": "ivan@example.com",
    "registered_at": "2024-01-15T08:30:00Z",
}
readers[2] = {
    "id": 2, "full_name": "Мария Петрова", "email": "maria@example.com",
    "registered_at": "2024-02-20T14:15:00Z",
}

loan_id_counter = [100]
book_id_counter = [2]
reader_id_counter = [2]


def now_iso():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def available_copies_for_book(book_id):
    book = books.get(book_id)
    if not book:
        return 0
    active = sum(1 for l in loans.values()
                 if l["book_id"] == book_id and l["returned_at"] is None)
    return max(0, book["total_copies"] - active)


def active_loans_for_reader(reader_id):
    return [l for l in loans.values()
            if l["reader_id"] == reader_id and l["returned_at"] is None]


def error(code, message, target=None, status=400):
    body = {"error": {"code": code, "message": message}}
    if target:
        body["error"]["target"] = target
    return json.dumps(body, ensure_ascii=False).encode("utf-8"), status, {
        "Content-Type": "application/json; charset=utf-8"}


def paginate(items, page, limit):
    total = len(items)
    start = (page - 1) * limit
    end = start + limit
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "limit": limit,
    }


class LibraryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return "__INVALID_JSON__"

    def _send(self, body, status=200, content_type="application/json"):
        if isinstance(body, dict):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            data = body
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self):
        path = urlparse(self.path).path
        method = self.command
        # Strip /v1 prefix
        if path.startswith("/v1/"):
            path = path[3:]
        return method, path

    def do_GET(self):
        _method, path = self._route()
        params = parse_qs(urlparse(self.path).query)

        if path == "/books":
            page = int(params.get("page", ["1"])[0])
            limit = int(params.get("limit", ["20"])[0])
            sort = params.get("sort", [None])[0]
            title_filter = params.get("title", [None])[0]
            author_filter = params.get("author", [None])[0]

            items = list(books.values())
            if title_filter:
                items = [b for b in items if title_filter.lower() in b["title"].lower()]
            if author_filter:
                items = [b for b in items if author_filter.lower() in b["author"].lower()]
            if sort:
                for field in reversed(sort.split(",")):
                    desc = field.startswith("-")
                    f = field.lstrip("-")
                    items.sort(key=lambda b: b.get(f, ""), reverse=desc)

            self._send(paginate(items, page, limit))
        elif path == "/readers":
            page = int(params.get("page", ["1"])[0])
            limit = int(params.get("limit", ["20"])[0])
            sort = params.get("sort", [None])[0]
            name_filter = params.get("full_name", [None])[0]
            email_filter = params.get("email", [None])[0]

            items = list(readers.values())
            if name_filter:
                items = [r for r in items if name_filter.lower() in r["full_name"].lower()]
            if email_filter:
                items = [r for r in items if email_filter.lower() in r["email"].lower()]
            if sort:
                for field in reversed(sort.split(",")):
                    desc = field.startswith("-")
                    f = field.lstrip("-")
                    items.sort(key=lambda r: r.get(f, ""), reverse=desc)

            self._send(paginate(items, page, limit))
        elif path == "/loans":
            page = int(params.get("page", ["1"])[0])
            limit = int(params.get("limit", ["20"])[0])
            sort = params.get("sort", [None])[0]
            status_filter = params.get("status", [None])[0]
            book_filter = params.get("book_id", [None])[0]
            reader_filter = params.get("reader_id", [None])[0]

            items = list(loans.values())
            if status_filter == "overdue":
                now = datetime.now(UTC)
                items = [l for l in items
                         if l["returned_at"] is None
                         and datetime.fromisoformat(l["due_date"]) < now]
            elif status_filter == "active":
                items = [l for l in items if l["returned_at"] is None]
            elif status_filter == "returned":
                items = [l for l in items if l["returned_at"] is not None]
            if book_filter:
                items = [l for l in items if str(l["book_id"]) == book_filter]
            if reader_filter:
                items = [l for l in items if str(l["reader_id"]) == reader_filter]
            if sort:
                for field in reversed(sort.split(",")):
                    desc = field.startswith("-")
                    f = field.lstrip("-")
                    items.sort(key=lambda l: l.get(f, ""), reverse=desc)

            self._send(paginate(items, page, limit))
        elif path.startswith("/books/"):
            book_id = int(path.split("/")[-1])
            book = books.get(book_id)
            if not book:
                body, status, headers = error("NOT_FOUND", "Книга не найдена", "book_id", 404)
                self._send(body, status, headers.get("Content-Type"))
                return
            book["available_copies"] = available_copies_for_book(book_id)
            self._send(book)
        elif path.startswith("/readers/"):
            reader_id = int(path.split("/")[-1])
            reader = readers.get(reader_id)
            if not reader:
                body, status, headers = error("NOT_FOUND", "Читатель не найден", "reader_id", 404)
                self._send(body, status, headers.get("Content-Type"))
                return
            self._send(reader)
        elif path.startswith("/loans/"):
            loan_id = int(path.split("/")[-1])
            loan = loans.get(loan_id)
            if not loan:
                body, status, headers = error("NOT_FOUND", "Выдача не найдена", "loan_id", 404)
                self._send(body, status, headers.get("Content-Type"))
                return
            self._send(loan)
        else:
            body, status, headers = error("NOT_FOUND", "Ресурс не найден", None, 404)
            self._send(body, status, headers.get("Content-Type"))

    def do_POST(self):
        _method, path = self._route()
        body = self._read_body()
        idempotency_key = self.headers.get("Idempotency-Key")

        if path == "/books":
            if body == "__INVALID_JSON__":
                b, s, h = error("INVALID_REQUEST", "Тело запроса не является валидным JSON", "body", 400)
                self._send(b, s, h.get("Content-Type"))
                return
            required = ["title", "author", "isbn", "published_year", "total_copies"]
            missing = [f for f in required if f not in body]
            if missing:
                b, s, h = error("VALIDATION_ERROR", f"Отсутствуют поля: {', '.join(missing)}", missing[0], 422)
                self._send(b, s, h.get("Content-Type"))
                return
            book_id_counter[0] += 1
            new_book = {
                "id": book_id_counter[0],
                "title": body["title"],
                "author": body["author"],
                "isbn": body["isbn"],
                "published_year": body["published_year"],
                "total_copies": body["total_copies"],
                "available_copies": body["total_copies"],
            }
            books[new_book["id"]] = new_book
            self._send(new_book, 201)

        elif path == "/readers":
            if body == "__INVALID_JSON__":
                b, s, h = error("INVALID_REQUEST", "Тело запроса не является валидным JSON", "body", 400)
                self._send(b, s, h.get("Content-Type"))
                return
            required = ["full_name", "email"]
            missing = [f for f in required if f not in body]
            if missing:
                b, s, h = error("VALIDATION_ERROR", f"Отсутствуют поля: {', '.join(missing)}", missing[0], 422)
                self._send(b, s, h.get("Content-Type"))
                return
            reader_id_counter[0] += 1
            new_reader = {
                "id": reader_id_counter[0],
                "full_name": body["full_name"],
                "email": body["email"],
                "registered_at": now_iso(),
            }
            readers[new_reader["id"]] = new_reader
            self._send(new_reader, 201)

        elif path == "/loans":
            # Idempotency check
            if idempotency_key:
                now_ts = datetime.now(UTC)
                if idempotency_key in idempotency_store:
                    stored_body, stored_response, stored_ts = idempotency_store[idempotency_key]
                    # TTL 24 hours
                    if (now_ts - stored_ts).total_seconds() > 86400:
                        del idempotency_store[idempotency_key]
                    else:
                        # Same key -> check body match
                        if stored_body != body:
                            b, s, h = error("IDEMPOTENCY_MISMATCH",
                                            "Тело запроса отличается от первого запроса с этим Idempotency-Key",
                                            "body", 409)
                            self._send(b, s, h.get("Content-Type"))
                            return
                        # Full replay
                        resp_data, resp_status = stored_response
                        self._send(resp_data, resp_status)
                        return

            if body == "__INVALID_JSON__":
                b, s, h = error("INVALID_REQUEST", "Тело запроса не является валидным JSON", "body", 400)
                self._send(b, s, h.get("Content-Type"))
                return
            required = ["book_id", "reader_id", "due_date"]
            missing = [f for f in required if f not in body]
            if missing:
                b, s, h = error("VALIDATION_ERROR", f"Отсутствуют поля: {', '.join(missing)}", missing[0], 422)
                self._send(b, s, h.get("Content-Type"))
                return

            book_id = body["book_id"]
            reader_id = body["reader_id"]
            due_date = body["due_date"]

            book = books.get(book_id)
            if not book:
                b, s, h = error("NOT_FOUND", "Книга не найдена", "book_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            reader = readers.get(reader_id)
            if not reader:
                b, s, h = error("NOT_FOUND", "Читатель не найден", "reader_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return

            # Business rule #1: available_copies > 0
            if available_copies_for_book(book_id) <= 0:
                b, s, h = error("BUSINESS_RULE_VIOLATION",
                                "Нет доступных экземпляров книги", "book_id", 409)
                self._send(b, s, h.get("Content-Type"))
                return

            # Business rule #2: max 5 active loans per reader
            active = active_loans_for_reader(reader_id)
            if len(active) >= 5:
                b, s, h = error("BUSINESS_RULE_VIOLATION",
                                "Превышен лимит активных выдач (5)", "reader_id", 409)
                self._send(b, s, h.get("Content-Type"))
                return

            # Business rule #6: due_date must be later than now
            try:
                due_dt = datetime.fromisoformat(due_date)
            except (ValueError, AttributeError):
                b, s, h = error("VALIDATION_ERROR", "Неверный формат due_date", "due_date", 422)
                self._send(b, s, h.get("Content-Type"))
                return
            if due_dt <= datetime.now(UTC):
                b, s, h = error("VALIDATION_ERROR",
                                "due_date должна быть позже текущей даты", "due_date", 422)
                self._send(b, s, h.get("Content-Type"))
                return

            loan_id_counter[0] += 1
            new_loan = {
                "id": loan_id_counter[0],
                "book_id": book_id,
                "reader_id": reader_id,
                "loaned_at": now_iso(),
                "due_date": due_date,
                "returned_at": None,
            }
            loans[new_loan["id"]] = new_loan

            # Store for idempotency
            if idempotency_key:
                idempotency_store[idempotency_key] = (body, (new_loan, 201), datetime.now(UTC))

            self._send(new_loan, 201)

        elif path.startswith("/loans/") and path.endswith("/return"):
            loan_id = int(path.split("/")[-2])
            loan = loans.get(loan_id)
            if not loan:
                b, s, h = error("NOT_FOUND", "Выдача не найдена", "loan_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            if loan["returned_at"] is not None:
                b, s, h = error("BUSINESS_RULE_VIOLATION",
                                "Книга уже возвращена по этой выдаче", "loan_id", 409)
                self._send(b, s, h.get("Content-Type"))
                return
            loan["returned_at"] = now_iso()
            self._send(loan)
        else:
            b, s, h = error("NOT_FOUND", "Ресурс не найден", None, 404)
            self._send(b, s, h.get("Content-Type"))

    def do_PUT(self):
        _method, path = self._route()
        body = self._read_body()

        if path.startswith("/books/"):
            book_id = int(path.split("/")[-1])
            book = books.get(book_id)
            if not book:
                b, s, h = error("NOT_FOUND", "Книга не найдена", "book_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            if body == "__INVALID_JSON__":
                b, s, h = error("INVALID_REQUEST", "Тело запроса не является валидным JSON", "body", 400)
                self._send(b, s, h.get("Content-Type"))
                return
            for field in ["title", "author", "isbn", "published_year", "total_copies"]:
                if field in body:
                    book[field] = body[field]
            book["available_copies"] = available_copies_for_book(book_id)
            self._send(book)
        elif path.startswith("/readers/"):
            reader_id = int(path.split("/")[-1])
            reader = readers.get(reader_id)
            if not reader:
                b, s, h = error("NOT_FOUND", "Читатель не найден", "reader_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            if body == "__INVALID_JSON__":
                b, s, h = error("INVALID_REQUEST", "Тело запроса не является валидным JSON", "body", 400)
                self._send(b, s, h.get("Content-Type"))
                return
            for field in ["full_name", "email"]:
                if field in body:
                    reader[field] = body[field]
            self._send(reader)
        else:
            b, s, h = error("NOT_FOUND", "Ресурс не найден", None, 404)
            self._send(b, s, h.get("Content-Type"))

    def do_DELETE(self):
        _method, path = self._route()

        if path.startswith("/books/"):
            book_id = int(path.split("/")[-1])
            book = books.get(book_id)
            if not book:
                b, s, h = error("NOT_FOUND", "Книга не найдена", "book_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            active = [l for l in loans.values()
                      if l["book_id"] == book_id and l["returned_at"] is None]
            if active:
                b, s, h = error("BUSINESS_RULE_VIOLATION",
                                "Нельзя удалить книгу: есть активные выдачи", "book_id", 409)
                self._send(b, s, h.get("Content-Type"))
                return
            del books[book_id]
            self.send_response(204)
            self.end_headers()
        elif path.startswith("/readers/"):
            reader_id = int(path.split("/")[-1])
            reader = readers.get(reader_id)
            if not reader:
                b, s, h = error("NOT_FOUND", "Читатель не найден", "reader_id", 404)
                self._send(b, s, h.get("Content-Type"))
                return
            active = active_loans_for_reader(reader_id)
            if active:
                b, s, h = error("BUSINESS_RULE_VIOLATION",
                                "Нельзя удалить читателя: есть активные выдачи", "reader_id", 409)
                self._send(b, s, h.get("Content-Type"))
                return
            del readers[reader_id]
            self.send_response(204)
            self.end_headers()
        else:
            b, s, h = error("NOT_FOUND", "Ресурс не найден", None, 404)
            self._send(b, s, h.get("Content-Type"))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), LibraryHandler)
    print("Mock Library API server running on http://localhost:8080")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()