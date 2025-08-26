from ultralytics import YOLO
import torch

def train_model():
    # 检查GPU是否可用
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"使用GPU进行训练: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device('cpu')
        print("警告: 未检测到GPU，使用CPU进行训练")

    model = YOLO('yolov12s.pt')
    model.to(device)

    print("开始训练模型...")
    results = model.train(
        data='chess_data.yaml',
        epochs=600,
        imgsz=640,
        lr0=0.001,
        lrf=0.01,
        scale=0.9,
        mixup=0.2,
        copy_paste=0.6,
        optimizer="AdamW",
        box=7.0,
        cls=2.0,
        hsv_h=0.2,
        hsv_s=0.5,
        hsv_v=0.5,
        degrees=0.0,
        translate=0.1,
        patience=600,
        augment=True,
        mosaic=1.0,
        batch=8,
        project='runs/train',
        name='chess_experiment_1',
        device=0
    )

    print("训练完成！")
    print(f"模型和结果保存在: {results.save_dir}")
    print("\n开始评估模型...")
    metrics = model.val()
    print("评估指标:")
    print(f"mAP50-95: {metrics.box.map}")
    print(f"mAP50: {metrics.box.map50}")

if __name__ == '__main__':
    train_model()