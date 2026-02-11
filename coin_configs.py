target_coins = [
    {"inst_id": "BTC-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 0.2, 'leverage': '100'},
    {"inst_id": "ETH-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 0.5, 'leverage': '100'},
    {"inst_id": "SOL-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 1, 'leverage': '50'},
    # {"inst_id": "XRP-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 4, 'sz': 1, 'leverage': '50'},
    # {"inst_id": "BNB-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 4, 'sz': 5, 'leverage': '50'},
]

USDT_MAX_LOSE_PER_TRADE = 2


evaluate_configs = {
    "begin": "2026-02-11 22:50:00"
}