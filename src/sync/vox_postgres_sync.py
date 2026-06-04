#!/usr/bin/env python3
"""
VOX PostgreSQL Sync Module
Replaces Supabase with direct PostgreSQL using psycopg2.
All scripts import this instead of vox_supabase_sync.
"""

import os
import json
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from contextlib import contextmanager

# -- Connection ---------------------------------------------------------------

def _get_conn_kwargs():
    """Build connection kwargs from env (Railway-style or local)."""
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and db_url.startswith("postgresql://"):
        parsed = urllib.parse.urlparse(db_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "user": parsed.username,
            "password": parsed.password,
            "dbname": parsed.path.lstrip("/"),
            "sslmode": "require",
        }
    # Fallback to individual Railway env vars
    return {
        "host": os.environ.get("PGHOST", "postgres-flpd.railway.internal"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "dbname": os.environ.get("PGDATABASE", "railway"),
        "sslmode": "require",
    }


@contextmanager
def _get_cursor():
    """Yield a RealDictCursor, auto-commit + close."""
    kwargs = _get_conn_kwargs()
    conn = psycopg2.connect(**kwargs)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# -- Helpers ------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_jsonb(val):
    """Convert Python list/dict to JSONB string for Postgres."""
    if val is None:
        return "[]"
    return json.dumps(val)


# -- CRUD: positions ----------------------------------------------------------

def get_positions():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM positions ORDER BY live_value DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_position(record: dict):
    """Insert or update a position by ticker."""
    sql = """
    INSERT INTO positions (ticker, shares, avg_cost, live_price, live_value, grade, council, brokers, sector, updated_at)
    VALUES (%(ticker)s, %(shares)s, %(avg_cost)s, %(live_price)s, %(live_value)s, %(grade)s, %(council)s, %(brokers)s::jsonb, %(sector)s, %(updated_at)s)
    ON CONFLICT (ticker) DO UPDATE SET
        shares = EXCLUDED.shares,
        avg_cost = EXCLUDED.avg_cost,
        live_price = EXCLUDED.live_price,
        live_value = EXCLUDED.live_value,
        grade = EXCLUDED.grade,
        council = EXCLUDED.council,
        brokers = EXCLUDED.brokers,
        sector = EXCLUDED.sector,
        updated_at = EXCLUDED.updated_at
    """
    record["brokers"] = _to_jsonb(record.get("brokers", []))
    record.setdefault("updated_at", _now_iso())
    with _get_cursor() as cur:
        cur.execute(sql, record)


def delete_positions_by_broker(broker_name: str):
    """Delete positions where brokers array contains broker_name."""
    with _get_cursor() as cur:
        cur.execute(
            "DELETE FROM positions WHERE brokers @> to_jsonb(%s::text)",
            ([broker_name],)
        )


def update_position(ticker: str, fields: dict):
    """Partial update of a position."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    sql = f"UPDATE positions SET {set_clause} WHERE ticker = %(ticker)s"
    fields["ticker"] = ticker
    with _get_cursor() as cur:
        cur.execute(sql, fields)


def get_position_by_ticker(ticker: str):
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE ticker = %s", (ticker,))
        row = cur.fetchone()
        return dict(row) if row else None


# -- CRUD: vox_grades (full 6-layer breakdown) --------------------------------

def save_vox_grade(record: dict):
    """Save a full 6-layer VOX grade breakdown."""
    sql = """
    INSERT INTO vox_grades (
        ticker, name, vox_grade, previous_grade, action, current_price,
        stop_loss, entry_point, position_value, shares,
        technical_score, fundamental_score, macro_score, sector_score,
        weather_score, sentiment_score, catalysts, weather_factors, generated_at
    ) VALUES (
        %(ticker)s, %(name)s, %(vox_grade)s, %(previous_grade)s, %(action)s, %(current_price)s,
        %(stop_loss)s, %(entry_point)s, %(position_value)s, %(shares)s,
        %(technical_score)s, %(fundamental_score)s, %(macro_score)s, %(sector_score)s,
        %(weather_score)s, %(sentiment_score)s, %(catalysts)s, %(weather_factors)s, %(generated_at)s
    )
    ON CONFLICT (ticker, generated_at) DO UPDATE SET
        vox_grade = EXCLUDED.vox_grade,
        action = EXCLUDED.action,
        current_price = EXCLUDED.current_price,
        stop_loss = EXCLUDED.stop_loss,
        entry_point = EXCLUDED.entry_point,
        position_value = EXCLUDED.position_value,
        shares = EXCLUDED.shares,
        technical_score = EXCLUDED.technical_score,
        fundamental_score = EXCLUDED.fundamental_score,
        macro_score = EXCLUDED.macro_score,
        sector_score = EXCLUDED.sector_score,
        weather_score = EXCLUDED.weather_score,
        sentiment_score = EXCLUDED.sentiment_score,
        catalysts = EXCLUDED.catalysts,
        weather_factors = EXCLUDED.weather_factors
    """
    record.setdefault("generated_at", _now_iso())
    with _get_cursor() as cur:
        cur.execute(sql, record)


def get_vox_grades():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM vox_grades ORDER BY vox_grade DESC")
        return [dict(r) for r in cur.fetchall()]


def get_vox_grade_by_ticker(ticker: str):
    with _get_cursor() as cur:
        cur.execute(
            "SELECT * FROM vox_grades WHERE ticker = %s ORDER BY generated_at DESC LIMIT 1",
            (ticker,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


# -- CRUD: watchlist ----------------------------------------------------------

def get_watchlist():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM watchlist ORDER BY grade DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_watchlist(record: dict):
    sql = """
    INSERT INTO watchlist (ticker, name, sector, thesis, entry_price, target_price, stop_loss, grade, council, status, added_at, notes)
    VALUES (%(ticker)s, %(name)s, %(sector)s, %(thesis)s, %(entry_price)s, %(target_price)s, %(stop_loss)s, %(grade)s, %(council)s, %(status)s, %(added_at)s, %(notes)s)
    ON CONFLICT (ticker) DO UPDATE SET
        name = EXCLUDED.name,
        sector = EXCLUDED.sector,
        thesis = EXCLUDED.thesis,
        entry_price = EXCLUDED.entry_price,
        target_price = EXCLUDED.target_price,
        stop_loss = EXCLUDED.stop_loss,
        grade = EXCLUDED.grade,
        council = EXCLUDED.council,
        status = EXCLUDED.status,
        notes = EXCLUDED.notes
    """
    record.setdefault("added_at", _now_iso())
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- CRUD: plays --------------------------------------------------------------

def get_plays():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM plays ORDER BY timestamp DESC")
        return [dict(r) for r in cur.fetchall()]


def insert_play(record: dict):
    sql = """
    INSERT INTO plays (timestamp, ticker, action, shares, price, notional, broker, reason, grade_at_entry, council_at_entry, notes, closed, exit_price, exit_date, pnl, pnl_pct)
    VALUES (%(timestamp)s, %(ticker)s, %(action)s, %(shares)s, %(price)s, %(notional)s, %(broker)s, %(reason)s, %(grade_at_entry)s, %(council_at_entry)s, %(notes)s, %(closed)s, %(exit_price)s, %(exit_date)s, %(pnl)s, %(pnl_pct)s)
    """
    record.setdefault("timestamp", _now_iso())
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- CRUD: alerts -------------------------------------------------------------

def get_alerts():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM alerts ORDER BY timestamp DESC")
        return [dict(r) for r in cur.fetchall()]


# -- CRUD: sector_momentum ----------------------------------------------------

def get_sector_momentum():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM sector_momentum ORDER BY updated_at DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_sector_momentum(record: dict):
    sql = """
    INSERT INTO sector_momentum (sector, momentum_score, trend, top_tickers, updated_at)
    VALUES (%(sector)s, %(momentum_score)s, %(trend)s, %(top_tickers)s::jsonb, %(updated_at)s)
    ON CONFLICT (sector) DO UPDATE SET
        momentum_score = EXCLUDED.momentum_score,
        trend = EXCLUDED.trend,
        top_tickers = EXCLUDED.top_tickers,
        updated_at = EXCLUDED.updated_at
    """
    record["top_tickers"] = _to_jsonb(record.get("top_tickers", []))
    record.setdefault("updated_at", _now_iso())
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- CRUD: weather_patterns ---------------------------------------------------

def get_weather_patterns():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM weather_patterns ORDER BY date DESC")
        return [dict(r) for r in cur.fetchall()]


def insert_weather_pattern(record: dict):
    sql = """
    INSERT INTO weather_patterns (date, regime, vix_level, spy_trend, notes, signals)
    VALUES (%(date)s, %(regime)s, %(vix_level)s, %(spy_trend)s, %(notes)s, %(signals)s::jsonb)
    """
    record["signals"] = _to_jsonb(record.get("signals", []))
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- CRUD: macro_signals ------------------------------------------------------

def get_macro_signals():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM macro_signals ORDER BY date DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_macro_signal(record: dict):
    sql = """
    INSERT INTO macro_signals (date, signal_type, strength, description, impact_sectors)
    VALUES (%(date)s, %(signal_type)s, %(strength)s, %(description)s, %(impact_sectors)s::jsonb)
    ON CONFLICT (date, signal_type) DO UPDATE SET
        strength = EXCLUDED.strength,
        description = EXCLUDED.description,
        impact_sectors = EXCLUDED.impact_sectors
    """
    record["impact_sectors"] = _to_jsonb(record.get("impact_sectors", []))
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- CRUD: technical_signals --------------------------------------------------

def get_technical_signals():
    with _get_cursor() as cur:
        cur.execute("SELECT * FROM technical_signals ORDER BY date DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_technical_signal(record: dict):
    sql = """
    INSERT INTO technical_signals (date, ticker, signal, timeframe, strength, notes)
    VALUES (%(date)s, %(ticker)s, %(signal)s, %(timeframe)s, %(strength)s, %(notes)s)
    ON CONFLICT (date, ticker, signal) DO UPDATE SET
        timeframe = EXCLUDED.timeframe,
        strength = EXCLUDED.strength,
        notes = EXCLUDED.notes
    """
    with _get_cursor() as cur:
        cur.execute(sql, record)


# -- Fake Supabase client (back-compat) ---------------------------------------

class _FakeSupabase:
    """Drop-in replacement for supabase.create_client().
    Routes table operations to PostgreSQL functions above.
    """

    def __init__(self):
        self._name = None
        self._filters = []
        self._order_col = None
        self._order_desc = False
        self._limit = None

    def table(self, name):
        self._name = name
        self._filters = []
        self._order_col = None
        self._order_desc = False
        self._limit = None
        return self

    def select(self, *cols):
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self._filters.append(("neq", col, val))
        return self

    def gt(self, col, val):
        self._filters.append(("gt", col, val))
        return self

    def lt(self, col, val):
        self._filters.append(("lt", col, val))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self._filters.append(("lte", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, vals))
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, record):
        self._insert_record = record
        return self

    def upsert(self, record, on_conflict=None):
        self._upsert_record = record
        return self

    def update(self, fields):
        self._update_fields = fields
        return self

    def delete(self):
        return self

    def execute(self):
        # Route select queries
        if not hasattr(self, "_insert_record") and not hasattr(self, "_upsert_record") and not hasattr(self, "_update_fields"):
            if self._name == "positions":
                if self._order_col == "live_value" and self._order_desc:
                    return type("R", (), {"data": get_positions()})()
                if any(f[1] == "ticker" for f in self._filters):
                    ticker = next(f[2] for f in self._filters if f[1] == "ticker")
                    row = get_position_by_ticker(ticker)
                    return type("R", (), {"data": [row] if row else []})()
                return type("R", (), {"data": get_positions()})()

            if self._name == "watchlist":
                return type("R", (), {"data": get_watchlist()})()

            if self._name == "plays":
                return type("R", (), {"data": get_plays()})()

            if self._name == "alerts":
                return type("R", (), {"data": get_alerts()})()

            if self._name == "sector_momentum":
                return type("R", (), {"data": get_sector_momentum()})()

            if self._name == "weather_patterns":
                return type("R", (), {"data": get_weather_patterns()})()

            if self._name == "macro_signals":
                return type("R", (), {"data": get_macro_signals()})()

            if self._name == "technical_signals":
                return type("R", (), {"data": get_technical_signals()})()

            return type("R", (), {"data": []})()

        # Handle insert
        if hasattr(self, "_insert_record"):
            if self._name == "plays":
                insert_play(self._insert_record)
            elif self._name == "weather_patterns":
                insert_weather_pattern(self._insert_record)
            return type("R", (), {"data": [self._insert_record]})()

        # Handle upsert
        if hasattr(self, "_upsert_record"):
            if self._name == "positions":
                if isinstance(self._upsert_record, list):
                    for r in self._upsert_record:
                        upsert_position(r)
                else:
                    upsert_position(self._upsert_record)
            elif self._name == "watchlist":
                if isinstance(self._upsert_record, list):
                    for r in self._upsert_record:
                        upsert_watchlist(r)
                else:
                    upsert_watchlist(self._upsert_record)
            elif self._name == "sector_momentum":
                upsert_sector_momentum(self._upsert_record)
            elif self._name == "macro_signals":
                upsert_macro_signal(self._upsert_record)
            elif self._name == "technical_signals":
                upsert_technical_signal(self._upsert_record)
            return type("R", (), {"data": [self._upsert_record]})()

        # Handle update
        if hasattr(self, "_update_fields"):
            if any(f[1] == "ticker" for f in self._filters):
                ticker = next(f[2] for f in self._filters if f[1] == "ticker")
                update_position(ticker, self._update_fields)
            return type("R", (), {"data": [self._update_fields]})()

        return type("R", (), {"data": []})()


def get_client():
    """Return a fake Supabase client that routes to PostgreSQL."""
    return _FakeSupabase()


# -- Test ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Testing PostgreSQL sync...")
    positions = get_positions()
    print(f"Loaded {len(positions)} positions from PostgreSQL")
    plays = get_plays()
    print(f"Loaded {len(plays)} plays from PostgreSQL")
