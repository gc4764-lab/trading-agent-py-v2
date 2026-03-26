# config/production.yaml
environment: production
log_level: INFO

database:
  host: postgres
  port: 5432
  name: trading_agent
  pool_size: 20
  max_overflow: 40

redis:
  host: redis
  port: 6379
  db: 0
  max_connections: 50

risk_management:
  max_position_size: 1000000
  max_daily_loss: 100000
  risk_per_trade: 0.01
  stop_loss_default: 0.02
  take_profit_default: 0.04
  max_drawdown: 0.15
  var_confidence: 0.95

trading:
  default_order_type: market
  min_volume_threshold: 1000
  max_slippage: 0.005
  execution_timeout: 30

ai:
  model: llama2
  host: http://ollama:11434
  confidence_threshold: 75
  analysis_interval: 3600

alerts:
  check_interval: 5
  max_alerts_per_symbol: 20
  webhook_timeout: 10
  webhook_retries: 3

monitoring:
  metrics_port: 9090
  health_check_port: 8080
  dashboard_port: 8500
  prometheus_url: http://prometheus:9090

security:
  rate_limit: 100
  rate_window: 60
  jwt_expiry: 3600
  encryption_key_file: /secrets/encryption.key

exchanges:
  binance:
    enabled: true
    api_key_env: BINANCE_API_KEY
    api_secret_env: BINANCE_API_SECRET
    testnet: false
  alpaca:
    enabled: true
    api_key_env: ALPACA_API_KEY
    api_secret_env: ALPACA_API_SECRET
    paper_trading: true
    