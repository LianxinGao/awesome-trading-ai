coin_configs = [
    # {"inst_id": "BTC-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 0.1, 'leverage': '100'},
    # {"inst_id": "XAUT-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 5, 'leverage': '100'}
    {"inst_id": "SOL-USDT-SWAP", "intervals": [15, 60], "limit": 200, "precision": 2, 'sz': 0.5, 'leverage': '50'},

]

monitoring_configs = [
    # {"inst_id": "BTC-USDT-SWAP", "interval": 15, "limit": 200, "precision": 2},
    {"inst_id": "SOL-USDT-SWAP", "interval": 15, "limit": 200, "precision": 2},
    # {"inst_id": "XAUT-USDT-SWAP", "interval": 15, "limit": 200, "precision": 2},

]

evaluate_configs = {
    "begin": "2026-01-13 12:00:00"
}