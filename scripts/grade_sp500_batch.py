#!/usr/bin/env python3
"""Grade a batch of S&P 500 tickers — designed for background execution"""
import os
import sys
from datetime import datetime

# Set env vars
os.environ['PGPASSWORD'] = 'hEJeasaJlhzFSVCIAgQqLDzqKCsUmqAS'
os.environ['PGHOST'] = 'acela.proxy.rlwy.net'
os.environ['PGPORT'] = '35577'
os.environ['PGUSER'] = 'postgres'
os.environ['PGDATABASE'] = 'railway'

sys.path.insert(0, os.path.expanduser('~/dev/vox-grader/src'))
from sync.vox_postgres_sync import _get_cursor
from grading.vox_engine import calculate_vox_grade
from psycopg2.extras import execute_values

def grade_batch(batch_size=20):
    print(f'[{datetime.now()}] Starting batch of {batch_size}...')
    
    with _get_cursor() as cur:
        cur.execute('''
            SELECT u.ticker 
            FROM sp500_universe u 
            LEFT JOIN sp500_grades g ON u.ticker = g.ticker 
            WHERE g.ticker IS NULL
            ORDER BY u.ticker
            LIMIT %s
        ''', (batch_size,))
        batch = [r['ticker'] for r in cur.fetchall()]
    
    if not batch:
        print('No more tickers to grade!')
        return 0
    
    print(f'Grading: {batch[0]} to {batch[-1]}')
    
    results = []
    for ticker in batch:
        try:
            result = calculate_vox_grade(ticker)
            results.append({
                'ticker': ticker,
                'vox_grade': result.overall_grade,
                'technical_score': result.technical_score,
                'fundamental_score': result.fundamental_score,
                'macro_score': result.macro_score,
                'sector_score': result.sector_score,
                'weather_score': result.weather_score,
                'sentiment_score': result.sentiment_score,
            })
            print(f'  {ticker}: Grade {result.overall_grade}')
        except Exception as e:
            print(f'  {ticker}: ERROR - {str(e)[:80]}')
    
    if results:
        with _get_cursor() as cur:
            rows = [(r['ticker'], r['vox_grade'], r['technical_score'], r['fundamental_score'],
                     r['macro_score'], r['sector_score'], r['weather_score'], r['sentiment_score'],
                     datetime.now()) for r in results]
            
            execute_values(cur, '''
                INSERT INTO sp500_grades (ticker, vox_grade, technical_score, fundamental_score, macro_score, sector_score, weather_score, sentiment_score, computed_at)
                VALUES %s
                ON CONFLICT (ticker) DO UPDATE SET
                    vox_grade = EXCLUDED.vox_grade,
                    technical_score = EXCLUDED.technical_score,
                    fundamental_score = EXCLUDED.fundamental_score,
                    macro_score = EXCLUDED.macro_score,
                    sector_score = EXCLUDED.sector_score,
                    weather_score = EXCLUDED.weather_score,
                    sentiment_score = EXCLUDED.sentiment_score,
                    computed_at = NOW()
            ''', rows)
        print(f'Saved {len(results)} grades')
    
    with _get_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM sp500_grades')
        total = cur.fetchone()['count']
        cur.execute('SELECT COUNT(*) FROM sp500_universe')
        universe = cur.fetchone()['count']
        print(f'Total graded: {total}/{universe} ({total/universe*100:.1f}%)')
    
    return len(batch)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--loops', type=int, default=1)
    args = parser.parse_args()
    
    for i in range(args.loops):
        print(f'\n=== Loop {i+1}/{args.loops} ===')
        graded = grade_batch(args.batch_size)
        if graded == 0:
            print('All done!')
            break
