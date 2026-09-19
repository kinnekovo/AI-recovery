from app.core.algorithm_config import config_entry, config_value


_SPEECH_RATE = config_value("speech_rate_reference")
_LOUDNESS = config_value("repeat_loudness_reference")
_ERRORS = config_value("error_count_reference")


PROCESS_METRIC_DEFINITIONS = {
    "script_accuracy": {
        "description": "正确生成字数 / 脚本总字数，用于衡量脚本输出完整性。",
        "unit": "%",
        "normal_range": {"target": config_value("script_accuracy_reference"), "operator": ">=", "config": config_entry("script_accuracy_reference")},
        "reference": f"工程参考 {config_value('script_accuracy_reference'):g}% 以上",
    },
    "error_count": {
        "description": "无意义重复、超过3秒停顿、难以理解发音和插入语的总次数。",
        "unit": "次",
        "normal_range": {**_ERRORS, "config": config_entry("error_count_reference")},
        "reference": f"工程参考 {_ERRORS['min']:g}-{_ERRORS['max']:g} 次",
    },
    "speech_rate": {
        "description": "有效交流字数 / 说话时间。",
        "unit": "字/min",
        "normal_range": {**_SPEECH_RATE, "config": config_entry("speech_rate_reference")},
        "reference": f"工程参考 {_SPEECH_RATE['min']:g}-{_SPEECH_RATE['max']:g} 字/min",
    },
    "loudness": {
        "description": "有效发声片段的相对数字响度；未经设备校准，不等同于临床 dBA。",
        "unit": "dBFS",
        "normal_range": {**_LOUDNESS, "config": config_entry("repeat_loudness_reference")},
        "reference": f"工程参考 {_LOUDNESS['min']:g} 至 {_LOUDNESS['max']:g} dBFS",
    },
}

PROCESS_METRIC_NAMES = set(PROCESS_METRIC_DEFINITIONS.keys())
PROCESS_REFERENCE_RANGES = {key: value["reference"] for key, value in PROCESS_METRIC_DEFINITIONS.items()}
