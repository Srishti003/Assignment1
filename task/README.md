# Transaction Webhook Processing Service

A high-performance, asynchronous Python service built with **FastAPI** and **SQLAlchemy** designed to ingest payment processor webhooks (such as RazorPay), acknowledge them in sub-50ms with `202 Accepted`, and process transactions reliably in the background with strict idempotency guarantees.

---

## 📋 Table of Contents
- [Architecture & Design Decisions](#-architecture--design-decisions)
- [Conceptual Mapping (.NET to Python)](#-conceptual-mapping-net-to-python)
- [Idempotency & Concurrency Strategy](#-idempotency--concurrency-strategy)
- [API Specification](#-api-specification)
- [Local Setup & Running](#-local-setup--running)
- [Running Automated Tests](#-running-automated-tests)
- [Cloud Deployment Guide](#-cloud-deployment-guide)
- [Example cURL Commands](#-example-curl-commands)

---

## 🏛 Architecture & Design Decisions

```
task/
├── app/
│   ├── config.py             # Application settings & environment configuration
│   ├── database.py           # Database engine & session management
│   ├── models.py             # SQLAlchemy ORM entity model
│   ├── schemas.py            # Pydantic request/response validation schemas
│   ├── crud.py               # Database queries & transactional state transitions
│   ├── services.py           # Background processing & external simulation worker
│   └── main.py               # FastAPI application, lifecycle, and route handlers
├── tests/
│   └── test_api.py           # Pytest unit & integration test suite
├── verify_service.py         # End-to-end 30s lifecycle verification script
├── Dockerfile                # Production multi-stage container definition
├── render.yaml               # Cloud deployment blueprint (Render)
├── Procfile                  # Procfile for PaaS platforms (Render, Railway, Heroku)
├── requirements.txt          # Python dependencies
└── pytest.ini                # Pytest configuration
```

### Technical Choices:
1. **Framework: FastAPI**
   - High-throughput asynchronous framework built on Starlette and Pydantic.
   - Native `async`/`await` event loop handles non-blocking I/O.
   - Built-in OpenAPI / Swagger documentation (`/docs`).
2. **Data Layer: SQLAlchemy ORM**
   - Clean abstraction supporting SQLite for local development and PostgreSQL for production cloud environments.
   - Thread-safe connection pooling and transactional isolation.
3. **Background Processing: FastAPI `BackgroundTasks` / Asynchronous Coroutines**
   - Decouples HTTP request acknowledgment from heavy computation/external calls.
   - Enables immediate response (< 50ms) well within the 500ms SLA.
   - Simulated 30-second delay uses `asyncio.sleep(30)`, which releases the thread and does not block concurrent HTTP traffic.
4. **Validation: Pydantic v2**
   - Strict compile/runtime input validation, guaranteeing payload integrity before hitting the database.

---

## 🔄 Conceptual Mapping (.NET to Python)

If you come from an **ASP.NET Core** background, here is how the building blocks correspond:

| ASP.NET Core (.NET) | FastAPI / SQLAlchemy (Python) | Role in this Project |
| :--- | :--- | :--- |
| **Minimal APIs / Controllers** | `@app.post()`, `@app.get()` routes | Route definition and HTTP verb binding |
| **Poco DTOs + FluentValidation** | Pydantic `BaseModel` | Request validation & automatic OpenAPI docs |
| **Entity Framework Core (`DbContext`)** | SQLAlchemy `SessionLocal` & declarative models | Database entity mapping and transactions |
| **Dependency Injection (`[FromServices]`)** | `Depends(get_db)` | Scoped lifetime injection of database sessions |
| **`BackgroundService` / `IHostedService`** | `BackgroundTasks` / `asyncio` worker | Background execution of long-running operations |
| **`appsettings.json` / `IOptions<T>`** | `BaseSettings` (`pydantic-settings`) | Strongly-typed environment configuration |
| **`Task.Delay(30000)`** | `await asyncio.sleep(30)` | Non-blocking asynchronous delay |

---

## 🛡 Idempotency & Concurrency Strategy

Payment processors like RazorPay can dispatch duplicate webhooks due to network retries, timeouts, or reconnections. This service implements a multi-tier defense:

1. **Unique Database Constraint (`transaction_id`)**:
   - The `transactions` table enforces a `UNIQUE` constraint and index on `transaction_id`.
2. **Atomic Ingestion Check**:
   - When a webhook arrives, the service first queries if the `transaction_id` already exists.
   - If found: The service immediately returns `202 Accepted` with an idempotent acknowledgment message and **does not** trigger another background task.
3. **Race Condition Prevention**:
   - If two identical webhooks hit the server at the exact same millisecond, the database unique constraint raises an `IntegrityError` on the second transaction.
   - The exception is handled gracefully: the session is rolled back, the existing record is recognized, and `202 Accepted` is returned without failing.
4. **State Machine (`PROCESSING` ➔ `PROCESSED`)**:
   - Transactions are created in `PROCESSING` status with `created_at` set.
   - After the 30-second processing window, the background worker transitions status to `PROCESSED` and sets `processed_at`.
   - If a webhook retry occurs while processing is still active, the status is not reset or interrupted.

---

## 📡 API Specification

### 1. Health Check
- **Endpoint**: `GET /`
- **Response Code**: `200 OK`
- **Response Body**:
  ```json
  {
    "status": "HEALTHY",
    "current_time": "2024-01-15T10:30:00Z"
  }
  ```

### 2. Transaction Webhook Ingestion
- **Endpoint**: `POST /v1/webhooks/transactions`
- **Response Code**: `202 Accepted` (Latency: `< 50ms`)
- **Request Body**:
  ```json
  {
    "transaction_id": "txn_abc123def456",
    "source_account": "acc_user_789",
    "destination_account": "acc_merchant_456",
    "amount": 1500,
    "currency": "INR"
  }
  ```
- **Response Body**:
  ```json
  {
    "status": "ACCEPTED",
    "message": "Transaction received and queued for processing",
    "transaction_id": "txn_abc123def456"
  }
  ```

### 3. Query Transaction Status
- **Endpoint**: `GET /v1/transactions/{transaction_id}`
- **Response Code**: `200 OK` (or `404 Not Found`)
- **Response Body**:
  ```json
  [
    {
      "transaction_id": "txn_abc123def456",
      "source_account": "acc_user_789",
      "destination_account": "acc_merchant_456",
      "amount": 1500.0,
      "currency": "INR",
      "status": "PROCESSED",
      "created_at": "2024-01-15T10:30:00Z",
      "processed_at": "2024-01-15T10:30:30Z"
    }
  ]
  ```

---

## 🚀 Local Setup & Running

### Option A: Using Python Virtual Environment

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd task
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the service**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access Swagger Documentation**:
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

---

### Option B: Using Docker

1. **Build the container**:
   ```bash
   docker build -t transaction-service .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8000:8000 transaction-service
   ```

---

## 🧪 Running Automated Tests

Run the full pytest suite (including latency checks, idempotency, lifecycle state transitions, and validation):
```bash
pytest -v
```

### Run End-to-End Live Verification Script
To observe the real 30-second background processing, idempotency, and state transition:
```bash
python verify_service.py
```

---

## ☁️ Cloud Deployment Guide

This repository is ready for zero-friction cloud deployment to platforms like **Render**, **Railway**, or **Koyeb**.

### Deploying to Render (Free Tier):
1. Push your repository to **GitHub**.
2. Go to [render.com](https://render.com) and click **New +** ➔ **Web Service**.
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Click **Create Web Service**. Your public endpoint will be live at `https://<your-service-name>.onrender.com`.

*(Optional: For persistent storage across multi-instance restarts in cloud, provision a free Managed PostgreSQL database on Render, Supabase, or Neon and set the `DATABASE_URL` environment variable).*

---

## 💻 Example cURL Commands

Replace `http://localhost:8000` with your deployed cloud URL:

```bash
# 1. Health Check
curl -X GET "http://localhost:8000/"

# 2. Ingest Transaction Webhook
curl -X POST "http://localhost:8000/v1/webhooks/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_test_101",
    "source_account": "acc_user_789",
    "destination_account": "acc_merchant_456",
    "amount": 1500,
    "currency": "INR"
  }'

# 3. Query Immediate Status (Status: PROCESSING)
curl -X GET "http://localhost:8000/v1/transactions/txn_test_101"

# 4. Duplicate Webhook (Idempotent - 202 Accepted without re-triggering job)
curl -X POST "http://localhost:8000/v1/webhooks/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_test_101",
    "source_account": "acc_user_789",
    "destination_account": "acc_merchant_456",
    "amount": 1500,
    "currency": "INR"
  }'

# 5. Query After 30 Seconds (Status: PROCESSED)
curl -X GET "http://localhost:8000/v1/transactions/txn_test_101"
```
