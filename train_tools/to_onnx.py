from ultralytics import YOLO

model = YOLO('best.pt')

success = model.export(format='onnx', 
                       imgsz=(640, 640),   # 输入图像尺寸，根据模型训练尺寸修改
                       dynamic=False,      # 是否使用动态维度
                       simplify=True,      # 是否简化 ONNX 模型
                       opset=12,
                       )

print(f"导出成功: {success}")