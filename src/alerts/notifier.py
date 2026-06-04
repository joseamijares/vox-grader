"""Alert system for portfolio monitoring."""
import os
from typing import Dict, List
from datetime import datetime


def send_telegram_alert(message: str) -> bool:
    """Send alert via Telegram bot."""
    try:
        import requests
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            print("⚠️  Telegram credentials not configured")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


def format_alert_message(alerts: List[Dict]) -> str:
    """Format alerts for Telegram."""
    lines = [
        "🚨 <b>VOX ALERTS</b>",
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ""
    ]
    
    for alert in alerts:
        emoji = "🟢" if alert['change_pct'] > 0 else "🔴"
        lines.append(
            f"{emoji} <b>{alert['ticker']}</b>: "
            f"{alert['change_pct']:+.1f}% @ ${alert['price']:.2f}"
        )
    
    return "\n".join(lines)


def check_stop_losses(sb_client, threshold: float = -20.0) -> List[Dict]:
    """Check positions approaching stop loss."""
    alerts = []
    
    resp = sb_client.table('positions').select('*').execute()
    for pos in resp.data:
        avg_cost = pos.get('avg_cost', 0) or 0
        live_price = pos.get('live_price', 0) or 0
        
        if avg_cost > 0 and live_price > 0:
            pnl_pct = ((live_price - avg_cost) / avg_cost) * 100
            
            if pnl_pct <= threshold:
                alerts.append({
                    'ticker': pos['ticker'],
                    'pnl_pct': pnl_pct,
                    'avg_cost': avg_cost,
                    'live_price': live_price,
                    'type': 'stop_loss'
                })
    
    return alerts


def check_daily_moves(sb_client, threshold: float = 10.0) -> List[Dict]:
    """Check for large daily price movements."""
    alerts = []
    
    resp = sb_client.table('positions').select('*').execute()
    for pos in resp.data:
        # Calculate change_pct from live_price vs avg_cost (fallback to 0)
        avg_cost = pos.get('avg_cost', 0) or 0
        live_price = pos.get('live_price', 0) or 0
        if avg_cost > 0 and live_price > 0:
            change_pct = ((live_price - avg_cost) / avg_cost) * 100
        else:
            change_pct = 0
        
        if abs(change_pct) >= threshold:
            alerts.append({
                'ticker': pos['ticker'],
                'change_pct': change_pct,
                'price': live_price,
                'type': 'daily_move'
            })
    
    return alerts


def run_daily_alerts(sb_client) -> Dict:
    """Run all alert checks and send notifications."""
    print("🔍 Running daily alert checks...\n")
    
    # Check stop losses
    stop_alerts = check_stop_losses(sb_client, threshold=-20.0)
    print(f"Stop loss alerts: {len(stop_alerts)}")
    
    # Check daily moves
    move_alerts = check_daily_moves(sb_client, threshold=10.0)
    print(f"Daily move alerts: {len(move_alerts)}")
    
    # Combine alerts
    all_alerts = stop_alerts + move_alerts
    
    if all_alerts:
        message = format_alert_message(all_alerts)
        sent = send_telegram_alert(message)
        
        return {
            'alerts_found': len(all_alerts),
            'telegram_sent': sent,
            'alerts': all_alerts
        }
    
    return {
        'alerts_found': 0,
        'telegram_sent': False,
        'alerts': []
    }
