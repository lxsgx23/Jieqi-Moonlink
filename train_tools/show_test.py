from ultralytics import YOLO
from PIL import Image

# 加载训练好的模型
model = YOLO('runs/train/chess_experiment_1/weights/best.pt')

# 对一张新的棋盘图片进行预测
results = model('test_board2.jpg')

for r in results:
    im_array = r.plot()  # 在图片上绘制边界框
    im = Image.fromarray(im_array[..., ::-1])
    im.show()
    im.save('results1.jpg')
    for box in r.boxes:
        class_id = int(box.cls)
        class_name = model.names[class_id]
        confidence = float(box.conf)
        print(f"检测到棋子: {class_name}, 置信度: {confidence:.2f}")