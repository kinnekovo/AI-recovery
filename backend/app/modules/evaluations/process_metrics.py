PROCESS_METRIC_DEFINITIONS = {
    "script_accuracy": {
        "description": "正确生成字数 / 脚本总字数，用于衡量脚本输出完整性。",
        "unit": "%",
        "normal_range": {"target": 90, "operator": ">="},
        "reference": "目标 90% 以上",
    },
    "error_count": {
        "description": "无意义重复、超过3秒停顿、难以理解发音和插入语的总次数。",
        "unit": "次",
        "normal_range": {"min": 0, "max": 1},
        "reference": "目标 0-1 次",
    },
    "speech_rate": {
        "description": "有效交流字数 / 说话时间。",
        "unit": "字/min",
        "normal_range": {"min": 180, "max": 240},
        "reference": "参考 180-240 字/min",
    },
    "loudness": {
        "description": "有效发声片段的相对数字响度；未经设备校准，不等同于临床 dBA。",
        "unit": "dBFS",
        "normal_range": {"min": -35, "max": -12},
        "reference": "工程参考 -35 至 -12 dBFS",
    },
}

PROCESS_METRIC_NAMES = set(PROCESS_METRIC_DEFINITIONS.keys())
PROCESS_REFERENCE_RANGES = {key: value["reference"] for key, value in PROCESS_METRIC_DEFINITIONS.items()}
