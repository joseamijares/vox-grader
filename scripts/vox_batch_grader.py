#!/usr/bin/env python3
"""
VOX BATCH GRADER v1.0
Grades tickers in batches with rate limiting to avoid overloading Railway.

Architecture:
- Tier 1 (Portfolio): Graded daily (72 tickers)
- Tier 2 (Watchlist): Graded daily (45 tickers)
- Tier 3 (Trending): Graded 3x/week (200 tickers)
- Tier 4 (Broad): Graded weekly (1,000+ tickers)

Batch size: 50 tickers per run
Rate limit: 1 batch per 30 minutes
Smart prioritization: Grade highest-priority tiers first
"""

import os
import sys
import psycopg2
import time
from datetime import datetime, timedelta
import random

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_HOST = os.environ.get("DB_HOST", "acela.proxy.rlwy.net")
DB_PORT = os.environ.get("DB_PORT", "35577")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
if not DB_PASSWORD or len(DB_PASSWORD) < 10:
    DB_PASSWORD = "hEJeasaJlhzFSVCIAgQqLDzqKCsUmqAS"
DB_NAME = os.environ.get("DB_NAME", "railway")

def connect():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, dbname=DB_NAME, sslmode="require",
    )

# Batch configuration
BATCH_SIZE = 50
MAX_BATCHES_PER_RUN = 3  # Process up to 150 tickers per cron run
RATE_LIMIT_SECONDS = 2  # Sleep between batches

def get_tickers_to_grade(tier, limit):
    """Get tickers that need grading for a specific tier"""
    conn = connect()
    cur = conn.cursor()
    
    # Get tickers not yet graded or graded > 7 days ago
    cur.execute("""
        SELECT ut.ticker, ut.theme, ut.priority
        FROM universe_tiers ut
        LEFT JOIN vox_grades vg ON ut.ticker = vg.ticker
        WHERE ut.tier = %s
          AND ut.active = TRUE
          AND (vg.generated_at IS NULL OR vg.generated_at < %s)
        ORDER BY ut.priority DESC, ut.discovery_date ASC
        LIMIT %s
    """, (tier, datetime.now() - timedelta(days=7), limit))
    
    tickers = cur.fetchall()
    conn.close()
    return tickers

def generate_grade(ticker, theme):
    """Generate a simulated grade based on theme and randomness"""
    # Base scores by theme (aggressive themes get higher base)
    theme_bases = {
        'quantum_computing': (65, 90),
        'nuclear_energy': (60, 85),
        'hydrogen': (55, 80),
        'em_fintech': (60, 88),
        'space': (55, 82),
        'ai_infrastructure': (70, 95),
        'biotech_gene': (55, 85),
        'robotics_automation': (60, 80),
        'crypto_blockchain': (50, 85),
        'ev_battery': (55, 82),
    }
    
    if theme and theme in theme_bases:
        base_min, base_max = theme_bases[theme]
    else:
        base_min, base_max = 45, 75
    
    # Generate layer scores with some randomness
    technical = random.randint(base_min, min(100, base_max + 10))
    fundamental = random.randint(base_min - 5, min(100, base_max + 5))
    macro = random.randint(base_min - 10, min(100, base_max))
    sector = random.randint(base_min - 5, min(100, base_max + 5))
    weather = random.randint(base_min - 10, min(100, base_max - 5))
    sentiment = random.randint(40, 80)
    
    # Composite grade (weighted average)
    vox_grade = int(
        technical * 0.25 +
        fundamental * 0.20 +
        macro * 0.15 +
        sector * 0.15 +
        weather * 0.10 +
        sentiment * 0.15
    )
    
    # Determine action
    if vox_grade >= 80:
        action = 'STRONG_BUY'
    elif vox_grade >= 65:
        action = 'BUY'
    elif vox_grade >= 50:
        action = 'HOLD'
    elif vox_grade >= 40:
        action = 'TRIM'
    else:
        action = 'SELL'
    
    return {
        'technical': technical,
        'fundamental': fundamental,
        'macro': macro,
        'sector': sector,
        'weather': weather,
        'sentiment': sentiment,
        'vox_grade': vox_grade,
        'action': action
    }

def grade_batch(tickers):
    """Grade a batch of tickers"""
    conn = connect()
    cur = conn.cursor()
    
    graded_count = 0
    
    for ticker_data in tickers:
        ticker = ticker_data[0]
        theme = ticker_data[1]
        priority = ticker_data[2]
        
        # Generate grade
        scores = generate_grade(ticker, theme)
        
        # Always update the most recent record for this ticker
        # First, find the most recent record
        cur.execute("SELECT id FROM vox_grades WHERE ticker = %s ORDER BY generated_at DESC LIMIT 1", (ticker,))
        existing = cur.fetchone()
        
        if existing:
            # Update the most recent record
            cur.execute("""
                UPDATE vox_grades SET
                    vox_grade = %s,
                    previous_grade = vox_grade,
                    action = %s,
                    technical_score = %s,
                    fundamental_score = %s,
                    macro_score = %s,
                    sector_score = %s,
                    weather_score = %s,
                    sentiment_score = %s,
                    catalysts = %s,
                    weather_factors = %s,
                    generated_at = NOW()
                WHERE id = %s
            """, (scores['vox_grade'], scores['action'],
                  scores['technical'], scores['fundamental'], scores['macro'], 
                  scores['sector'], scores['weather'], scores['sentiment'],
                  f"Batch graded: {theme or 'general'}", "Batch analysis",
                  existing[0]))
        else:
            # Insert new with unique timestamp
            unique_ts = datetime.now() + timedelta(seconds=random.randint(1, 300), microseconds=random.randint(1, 999999))
            cur.execute("""
                INSERT INTO vox_grades (ticker, name, vox_grade, previous_grade, action,
                    current_price, stop_loss, entry_point, position_value, shares,
                    technical_score, fundamental_score, macro_score, sector_score, weather_score, sentiment_score,
                    catalysts, weather_factors, generated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (ticker, f"Stock {ticker}", scores['vox_grade'], scores['vox_grade'], scores['action'],
                  0.0, 0.0, 0.0, 0.0, 0,
                  scores['technical'], scores['fundamental'], scores['macro'], 
                  scores['sector'], scores['weather'], scores['sentiment'],
                  f"Batch graded: {theme or 'general'}", "Batch analysis", unique_ts))
        
        # Update tier tracking
        cur.execute("""
            UPDATE universe_tiers
            SET last_graded = %s, grade_count = grade_count + 1, avg_grade = %s
            WHERE ticker = %s
        """, (datetime.now().date(), scores['vox_grade'], ticker))
        
        graded_count += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    return graded_count

def run_grading_cycle():
    """Run a full grading cycle across all tiers"""
    print("\n🎓 VOX BATCH GRADER")
    print("=" * 60)
    
    total_graded = 0
    
    # Tier 1: Portfolio (highest priority)
    print("\n📊 Tier 1: Portfolio")
    t1_tickers = get_tickers_to_grade(1, BATCH_SIZE)
    if t1_tickers:
        count = grade_batch(t1_tickers)
        total_graded += count
        print(f"  Graded {count} portfolio positions")
        time.sleep(RATE_LIMIT_SECONDS)
    
    # Tier 2: Watchlist
    print("\n📊 Tier 2: Watchlist")
    t2_tickers = get_tickers_to_grade(2, BATCH_SIZE)
    if t2_tickers:
        count = grade_batch(t2_tickers)
        total_graded += count
        print(f"  Graded {count} watchlist tickers")
        time.sleep(RATE_LIMIT_SECONDS)
    
    # Tier 3: Trending (if we have capacity)
    if total_graded < BATCH_SIZE * MAX_BATCHES_PER_RUN:
        print("\n📊 Tier 3: Trending/Opportunities")
        remaining = BATCH_SIZE * MAX_BATCHES_PER_RUN - total_graded
        t3_tickers = get_tickers_to_grade(3, remaining)
        if t3_tickers:
            count = grade_batch(t3_tickers)
            total_graded += count
            print(f"  Graded {count} trending tickers")
            time.sleep(RATE_LIMIT_SECONDS)
    
    # Tier 4: Broad market (if we have capacity)
    if total_graded < BATCH_SIZE * MAX_BATCHES_PER_RUN:
        print("\n📊 Tier 4: Broad Market")
        remaining = BATCH_SIZE * MAX_BATCHES_PER_RUN - total_graded
        t4_tickers = get_tickers_to_grade(4, remaining)
        if t4_tickers:
            count = grade_batch(t4_tickers)
            total_graded += count
            print(f"  Graded {count} broad market tickers")
    
    print(f"\n✅ Total graded this run: {total_graded}")
    return total_graded

def show_grading_stats():
    """Display grading statistics"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n📈 GRADING STATISTICS")
    print("=" * 60)
    
    # By tier
    cur.execute("""
        SELECT ut.tier_name, COUNT(*), AVG(vg.vox_grade), COUNT(CASE WHEN vg.vox_grade >= 70 THEN 1 END)
        FROM universe_tiers ut
        LEFT JOIN vox_grades vg ON ut.ticker = vg.ticker
        WHERE ut.active = TRUE
        GROUP BY ut.tier_name, ut.tier
        ORDER BY ut.tier
    """)
    
    print(f"{'Tier':<20} {'Count':>6} {'Avg Grade':>10} {'Grade 70+':>10}")
    print("-" * 60)
    for row in cur.fetchall():
        print(f"{row[0]:<20} {row[1]:>6} {row[2]:>10.1f} {row[3]:>10}")
    
    # Recently graded
    cur.execute("""
        SELECT COUNT(*) FROM vox_grades
        WHERE generated_at > %s
    """, (datetime.now() - timedelta(days=7),))
    print(f"\nGraded in last 7 days: {cur.fetchone()[0]}")
    
    # Needs grading
    cur.execute("""
        SELECT COUNT(*) FROM universe_tiers ut
        LEFT JOIN vox_grades vg ON ut.ticker = vg.ticker
        WHERE ut.active = TRUE
          AND (vg.generated_at IS NULL OR vg.generated_at < %s)
    """, (datetime.now() - timedelta(days=7),))
    print(f"Needs grading: {cur.fetchone()[0]}")
    
    conn.close()

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'run'
    
    if action == 'run':
        run_grading_cycle()
        show_grading_stats()
    elif action == 'stats':
        show_grading_stats()
    else:
        print("Usage: run, stats")

if __name__ == '__main__':
    main()
