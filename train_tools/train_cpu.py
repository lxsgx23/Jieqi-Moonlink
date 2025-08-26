from ultralytics import YOLO

def train_model():

    model = YOLO('yolov8n.pt')

    print("开始训练模型...")
    results = model.train(
        data='chess_data.yaml',
        epochs=100,
        imgsz=640,
        batch=8,
        project='runs/train',
        name='chess_experiment_1'
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