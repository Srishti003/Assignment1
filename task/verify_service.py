"""
Verification script demonstrating the end-to-end lifecycle:
1. Health check
2. Webhook ingestion (< 500ms response)
3. Immediate status verification (status: PROCESSING, processed_at: null)
4. Duplicate webhook idempotency check
5. Post-delay verification (status: PROCESSED, processed_at: timestamp)
"""
import asyncio
import time
from httpx import AsyncClient, ASGITransport
from app.main import app


async def run_verification():
    print("=" * 60)
    print("STARTING END-TO-END VERIFICATION")
    print("=" * 60)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        print("\n1. Testing GET / (Health Check)...")
        res = await client.get("/")
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200
        assert res.json()["status"] == "HEALTHY"

        # 2. Webhook Ingestion
        txn_id = f"txn_live_{int(time.time())}"
        payload = {
            "transaction_id": txn_id,
            "source_account": "acc_user_789",
            "destination_account": "acc_merchant_456",
            "amount": 1500,
            "currency": "INR",
        }
        print(f"\n2. Posting Webhook for {txn_id}...")
        start_time = time.perf_counter()
        webhook_res = await client.post("/v1/webhooks/transactions", json=payload)
        latency_ms = (time.perf_counter() - start_time) * 1000

        print(f"Status Code: {webhook_res.status_code} (Expected 202)")
        print(f"Latency: {latency_ms:.2f} ms (Must be < 500ms)")
        print(f"Response: {webhook_res.json()}")
        assert webhook_res.status_code == 202
        assert latency_ms < 500

        # 3. Query Immediate Status (PROCESSING)
        print(f"\n3. Querying immediate status for {txn_id}...")
        status_res = await client.get(f"/v1/transactions/{txn_id}")
        print(f"Status Code: {status_res.status_code}")
        print(f"Response: {status_res.json()}")
        assert status_res.status_code == 200
        data = status_res.json()[0]
        assert data["status"] == "PROCESSING"
        assert data["processed_at"] is None

        # 4. Duplicate Webhook (Idempotency)
        print(f"\n4. Sending duplicate webhook for {txn_id}...")
        dup_res = await client.post("/v1/webhooks/transactions", json=payload)
        print(f"Duplicate Status Code: {dup_res.status_code} (Expected 202)")
        print(f"Response: {dup_res.json()}")
        assert dup_res.status_code == 202

        # 5. Wait for Background Worker (simulated 30s)
        print("\n5. Waiting 31 seconds for background processing to finish...")
        for remaining in range(31, 0, -5):
            print(f"   Waiting... {remaining} seconds remaining")
            await asyncio.sleep(5)

        # 6. Final Status Check (PROCESSED)
        print(f"\n6. Querying final status for {txn_id}...")
        final_res = await client.get(f"/v1/transactions/{txn_id}")
        print(f"Final Status Code: {final_res.status_code}")
        print(f"Response: {final_res.json()}")
        assert final_res.status_code == 200
        final_data = final_res.json()[0]
        assert final_data["status"] == "PROCESSED"
        assert final_data["processed_at"] is not None
        print(f"\n[SUCCESS] Transaction processed at {final_data['processed_at']}!")

    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_verification())
