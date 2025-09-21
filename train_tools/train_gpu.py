from ultralytics import YOLO
import torch
import argparse

def train_model(profile=False):
    # 检查GPU是否可用
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print(f"使用GPU进行训练: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device('cpu')
        print("警告: 未检测到GPU，使用CPU进行训练（速度会很慢）")

    # 1. 加载预训练的YOLOv8n模型
    model = YOLO('yolov12n.pt')
    
    # 将模型移动到相应设备
    model.to(device)

    # 2. 开始训练
    print("开始训练模型...")
    results = model.train(
        data='chess_data.yaml',
        epochs=700,
        imgsz=640,
        lr0=0.001,
        lrf=0.01,
        
        scale=0.9,
        mixup=0.2,
        copy_paste=0.6,
        optimizer="AdamW",
        box=7.0,  # 提高定位权重
        cls=2.0,   # 提高分类权重
        hsv_h=0.2,   # 限制色调增强幅度
        hsv_s=0.5,   # 限制饱和度增强幅度
        hsv_v=0.5,   # 限制亮度增强幅度
        degrees=0.0,  # 限制旋转角度
        translate=0.1,  # 限制平移幅度
        patience=700,
        augment=True,
        mosaic=1.0,
        batch=-1,
        amp=False,
        pretrained=True,
        project='runs/train',
        name='chess_experiment_1',
        device=0,  # 指定使用GPU 0，如果有多个GPU可以使用列表如[0,1]
        profile=True  # 添加profile选项
    )

    print("训练完成！")
    print(f"模型和结果保存在: {results.save_dir}")

    # (可选) 3. 在验证集上评估模型性能
    print("\n开始评估模型...")
    metrics = model.val()
    print("评估指标:")
    print(f"mAP50-95: {metrics.box.map}")
    print(f"mAP50: {metrics.box.map50}")

if __name__ == '__main__':
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='训练中国象棋揭棋棋盘YOLO模型')
    parser.add_argument('--profile', action='store_true', help='启用性能分析')
    
    # 解析参数
    args = parser.parse_args()
    
    # 调用训练函数并传递profile参数
    train_model(profile=args.profile)