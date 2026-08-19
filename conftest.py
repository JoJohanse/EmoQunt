"""pytest 配置：排除顶层脚本，避免 import 时污染测试采集。"""

collect_ignore = ["test/test_ak.py", "test/check_cuda.py"]
