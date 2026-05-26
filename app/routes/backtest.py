from flask import Blueprint, render_template, request, jsonify
from app.models.backtest import BacktestEngine
from datetime import datetime, timedelta

bp = Blueprint('backtest', __name__, url_prefix='/backtest')

@bp.route('/')
def index():
    """
    Render the backtest dashboard.
    Default parameters:
    - Ticker: 2330.TW (TSMC)
    - Date range: Last 1 year
    - Stop Loss: 5%
    - Take Profit: 10%
    """
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    return render_template(
        'backtest/index.html',
        default_start=start_date,
        default_end=end_date
    )

@bp.route('/api/run', methods=['POST'])
def run_api():
    """
    Run backtest via API and return JSON results.
    Expected payload (Form or JSON):
    - ticker (str)
    - start_date (str)
    - end_date (str)
    - strategy (str)
    - stop_loss_pct (float)
    - take_profit_pct (float)
    """
    # Parse request parameters
    if request.is_json:
        data = request.json
    else:
        data = request.form
        
    ticker = data.get('ticker', '2330.TW').strip().upper()
    start_date = data.get('start_date', '').strip()
    end_date = data.get('end_date', '').strip()
    strategy = data.get('strategy', 'KD').strip()
    
    try:
        stop_loss_pct = float(data.get('stop_loss_pct', 5.0))
        take_profit_pct = float(data.get('take_profit_pct', 10.0))
    except ValueError:
        return jsonify({
            'success': False,
            'error': "停損或停利百分比必須是數值。"
        }), 400
        
    # Basic validation
    if not ticker:
        return jsonify({'success': False, 'error': "股票代碼不能為空。"}), 400
    if not start_date or not end_date:
        return jsonify({'success': False, 'error': "請選擇起訖日期。"}), 400
        
    try:
        # Validate date formats
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'success': False, 'error': "日期格式必須為 YYYY-MM-DD。"}), 400
        
    # Run the backtest
    results = BacktestEngine.run_backtest(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        strategy=strategy,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )
    
    if not results.get('success', False):
        return jsonify(results), 400
        
    return jsonify(results)
