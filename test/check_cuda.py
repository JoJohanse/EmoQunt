import torch
import transformers
import modelscope

# 检查PyTorch版本和CUDA可用性
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA是否可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA设备数量: {torch.cuda.device_count()}")
    print(f"当前CUDA设备: {torch.cuda.current_device()}")
    print(f"CUDA设备名称: {torch.cuda.get_device_name(torch.cuda.current_device())}")
    print(f"CUDA版本: {torch.version.cuda}")

# 检查transformers版本
print(f"Transformers版本: {transformers.__version__}")

# 检查modelscope版本
print(f"ModelScope版本: {modelscope.__version__}")

# 检查modelscope的CUDA检测
print("\nModelScope CUDA检测:")
try:
    from modelscope.utils.device import get_device
    print(f"ModelScope检测到的设备: {get_device()}")
except Exception as e:
    print(f"获取ModelScope设备信息失败: {e}")