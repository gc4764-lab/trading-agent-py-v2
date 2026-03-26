#example 1
# Place a market order
result = await place_market_order("BTCUSD", "buy", 0.1)

# Create a price alert
result = await create_price_alert("ETHUSD", "above", 3500, "notify")

# Create an alert that places an order
result = await create_alert_with_order(
    symbol="AAPL",
    condition="below",
    price=170,
    order_side="buy",
    order_type="limit",
    quantity=10
)

# Get AI trading advice
analysis = await ai_trading_advice("BTCUSD")

