import random

def detect_upset():
    if random.random() > 0.7:
        return [
            "Sevilla 可能爆冷 Barcelona",
            "Milan 有機會擊敗 Inter"
        ]
    return []
