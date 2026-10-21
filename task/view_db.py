"""
Convenient CLI utility to inspect transactions in the database.
Usage: python view_db.py
"""
import sqlite3
import os


def show_transactions():
    db_path = "transactions.db"
    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' not found yet. Start the app or run tests first.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, transaction_id, source_account, destination_account, amount, currency, status, created_at, processed_at FROM transactions ORDER BY id DESC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error querying database: {e}")
        return
    finally:
        conn.close()

    if not rows:
        print("Database connected: No transactions found yet.")
        return

    print("=" * 125)
    print(f"{'ID':<4} | {'TRANSACTION ID':<22} | {'AMOUNT':<10} | {'STATUS':<11} | {'CREATED AT':<20} | {'PROCESSED AT':<20}")
    print("=" * 125)
    for r in rows:
        txn_id = r[1]
        amt = f"{r[4]} {r[5]}"
        status = r[6]
        created = str(r[7])[:19] if r[7] else "-"
        processed = str(r[8])[:19] if r[8] else "(processing...)"
        print(f"{r[0]:<4} | {txn_id:<22} | {amt:<10} | {status:<11} | {created:<20} | {processed:<20}")
    print("=" * 125)
    print(f"Total Transactions: {len(rows)}\n")


if __name__ == "__main__":
    show_transactions()
