# db.py
import sqlite3
import os
import json

DB_PATH = "panel_cache.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # -----------------------------------------------------
    # RAW WEATHER + PM25 TABLE
    # -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS panel_data (
            panel_id TEXT NOT NULL,
            date TEXT NOT NULL,      
            allsky_kt REAL,
            prectotcorr REAL,
            t2m REAL,
            ws10m REAL,
            ws50m REAL,
            pm25 REAL,
            PRIMARY KEY (panel_id, date)
        );
    """)

    # -----------------------------------------------------
    # LSTM WINDOW CACHE
    # -----------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lstm_cache (
            panel_id TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            predictions_json TEXT NOT NULL,
            PRIMARY KEY (panel_id, start_date, end_date)
        );
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------
# RAW WEATHER UPSERT
# ---------------------------------------------------------
def upsert_panel_day(panel_id, date, row):
    upsert_panel_days(panel_id, [{"date": date, **row}])


def upsert_panel_days(panel_id, rows):
    """Batch upsert weather/PM2.5 rows (one transaction)."""
    if not rows:
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT OR REPLACE INTO panel_data (
            panel_id, date,
            allsky_kt, prectotcorr, t2m,
            ws10m, ws50m, pm25
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                panel_id,
                r["date"],
                r.get("ALLSKY_KT"),
                r.get("PRECTOTCORR"),
                r.get("T2M"),
                r.get("WS10M"),
                r.get("WS50M"),
                r.get("PM25"),
            )
            for r in rows
        ],
    )
    conn.commit()
    conn.close()


def get_panel_data(panel_id, start_date, end_date):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM panel_data
        WHERE panel_id = ?
          AND date BETWEEN ? AND ?
        ORDER BY date
    """, (panel_id, start_date, end_date))

    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ---------------------------------------------------------
# LSTM CACHE SUPPORT
# ---------------------------------------------------------
def save_lstm_cache(panel_id, start_date, end_date, predictions):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO lstm_cache (
            panel_id, start_date, end_date, predictions_json
        )
        VALUES (?, ?, ?, ?)
    """, (
        panel_id, start_date, end_date,
        json.dumps(predictions)
    ))

    conn.commit()
    conn.close()



def load_lstm_cache(panel_id, start_date, end_date):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT predictions_json
        FROM lstm_cache
        WHERE panel_id = ?
          AND start_date = ?
          AND end_date = ?
    """, (panel_id, start_date, end_date))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return json.loads(row["predictions_json"])
