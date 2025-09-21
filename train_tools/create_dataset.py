# encoding: utf-8
import os  # 导入操作系统接口模块，用于文件和目录操作
import random  # 导入随机数生成模块，用于随机选择和打乱数据
from PIL import Image  # 从PIL库导入Image模块，用于图像处理
from PIL import ImageEnhance
import shutil  # 导入shutil模块，用于高级文件操作

PIECES_DIR = "pieces"  # 定义棋子图片存放目录
PIECES_DIR_SECOND = "NewPieces"
BOARD_DIR = "board"  # 定义棋盘图片存放目录
OUTPUT_DIR = "datasets"  # 定义输出数据集目录
BOARD_WIDTH, BOARD_HEIGHT = 628, 693  # 定义棋盘图片的宽度和高度（像素）
PIECE_WIDTH, PIECE_HEIGHT = 70, 70  # 定义棋子图片的宽度和高度（像素）
NUM_COLS = 9  # 定义棋盘列数（象棋棋盘为9列）
NUM_ROWS = 10  # 定义棋盘行数（象棋棋盘为10行）

NUM_TRAIN_IMAGES = 2500  # 定义训练集图片数量
NUM_VAL_IMAGES = 500  # 定义验证集图片数量

piece_types = ['P', 'R', 'K', 'N', 'C', 'A', 'B', 'X']  # 定义棋子类型列表：兵、车、将、马、炮、仕、相、无棋子
colors = ['r', 'b']  # 定义棋子颜色列表：红色、黑色
CLASS_NAMES = [f"{c}{p}" for c in colors for p in piece_types] + ['board']  # 生成所有棋子类别名称的组合（颜色+棋子类型）+ 棋盘区域
CLASS_MAP = {name: i for i, name in enumerate(CLASS_NAMES)}  # 创建类别名称到类别ID的映射字典

# 定义棋盘文件对应的区域坐标 (x1, y1, x2, y2)
BOARD_REGIONS = {
    'board.png': (41, 41, 583, 651),
    'board2.png': (195, 136, 578, 564)
}


def get_grid_coordinates(board_width, board_height, num_cols, num_rows):  # 定义函数：计算棋盘网格坐标点

    coords = []  # 初始化坐标列表
    margin_x = board_width * 0.05  # 计算水平边距（棋盘宽度的5%）
    margin_y = board_height * 0.05  # 计算垂直边距（棋盘高度的5%）
    grid_width = (board_width - 2 * margin_x) / (num_cols - 1)  # 计算网格单元的宽度
    grid_height = (board_height - 2 * margin_y) / (num_rows - 1)  # 计算网格单元的高度

    for i in range(num_rows):  # 遍历每一行
        for j in range(num_cols):  # 遍历每一列
            x = int(margin_x + j * grid_width)  # 计算当前网格点的x坐标
            y = int(margin_y + i * grid_height)  # 计算当前网格点的y坐标
            coords.append((x, y))  # 将坐标点添加到坐标列表中
    return coords  # 返回所有网格坐标点

def yolo_format(class_id, center_x, center_y, width, height, image_width, image_height):  # 定义函数：将标注转换为YOLO格式
    x = center_x / image_width  # 将中心点x坐标归一化到[0,1]范围
    y = center_y / image_height  # 将中心点y坐标归一化到[0,1]范围
    w = width / image_width  # 将宽度归一化到[0,1]范围
    h = height / image_height  # 将高度归一化到[0,1]范围
    return f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n"  # 返回YOLO格式的标注字符串

def create_dataset():  # 定义主函数：创建数据集

    if os.path.exists(OUTPUT_DIR):  # 检查输出目录是否存在
        shutil.rmtree(OUTPUT_DIR)  # 如果存在则删除整个目录（清理旧数据）
    for split in ['train', 'val']:  # 遍历数据集划分（训练集和验证集）
        os.makedirs(os.path.join(OUTPUT_DIR, 'images', split), exist_ok=True)  # 创建图片存放目录
        os.makedirs(os.path.join(OUTPUT_DIR, 'labels', split), exist_ok=True)  # 创建标签存放目录
    board_files = [os.path.join(BOARD_DIR, f) for f in os.listdir(BOARD_DIR) if f.endswith('.png')]  # 获取所有棋盘图片文件路径
    
    # 从两个目录获取棋子文件
    piece_files_dir1 = [f for f in os.listdir(PIECES_DIR) if f.endswith('.png')]  # 获取第一个目录的棋子
    piece_files_dir2 = [f for f in os.listdir(PIECES_DIR_SECOND) if f.endswith('.png')]  # 获取第二个目录的棋子
    
    print(f"从 {PIECES_DIR} 目录加载 {len(piece_files_dir1)} 个棋子文件")
    print(f"从 {PIECES_DIR_SECOND} 目录加载 {len(piece_files_dir2)} 个棋子文件")
    
    piece_info = {}  # 初始化棋子信息字典
    
    # 处理第一个目录的棋子文件
    for f in piece_files_dir1:  # 遍历第一个目录的每个棋子文件
        color = f[0]  # 从文件名提取颜色信息（第一个字符）
        piece_type = f[1]  # 从文件名提取棋子类型信息（第二个字符）
        class_name = f"{color}{piece_type}"  # 组合生成类别名称
        if class_name in piece_info:  # 如果该类别已存在
            piece_info[class_name].append(os.path.join(PIECES_DIR, f))  # 将文件路径添加到现有列表
        else:  # 如果该类别不存在
            piece_info[class_name] = [os.path.join(PIECES_DIR, f)]  # 创建新的类别列表
    
    # 处理第二个目录的棋子文件
    for f in piece_files_dir2:  # 遍历第二个目录的每个棋子文件
        color = f[0]  # 从文件名提取颜色信息（第一个字符）
        piece_type = f[1]  # 从文件名提取棋子类型信息（第二个字符）
        class_name = f"{color}{piece_type}"  # 组合生成类别名称
        if class_name in piece_info:  # 如果该类别已存在
            piece_info[class_name].append(os.path.join(PIECES_DIR_SECOND, f))  # 将文件路径添加到现有列表
        else:  # 如果该类别不存在
            piece_info[class_name] = [os.path.join(PIECES_DIR_SECOND, f)]  # 创建新的类别列表
    
    # 显示每个棋子类型的可用选项数量
    print("\n各棋子类型的可用选项数量：")
    for class_name, paths in piece_info.items():
        print(f"  {class_name}: {len(paths)} 个选项")
    
    grid_coords = get_grid_coordinates(BOARD_WIDTH, BOARD_HEIGHT, NUM_COLS, NUM_ROWS)  # 获取棋盘所有网格坐标点

    for split in ['train', 'val']:  # 遍历数据集划分
        num_images = NUM_TRAIN_IMAGES if split == 'train' else NUM_VAL_IMAGES  # 根据划分类型确定生成图片数量
        print(f"--- Generating {split} data ---")  # 打印当前生成的数据集类型

        for i in range(num_images):  # 遍历生成每张图片
            board_path = random.choice(board_files)  # 随机选择一个棋盘图片
            board_img = Image.open(board_path).convert("RGBA")  # 打开棋盘图片并转换为RGBA格式
            num_pieces_to_place = random.randint(15, 40)  # 随机决定要放置的棋子数量（5-32个）
            random.shuffle(grid_coords)  # 随机打乱网格坐标顺序
            placement_positions = grid_coords[:num_pieces_to_place]  # 选择前N个位置作为棋子放置位置
            
            yolo_labels = []  # 初始化YOLO标签列表
            
            # 添加棋盘区域标注
            board_filename = os.path.basename(board_path)
            if board_filename in BOARD_REGIONS:
                x1, y1, x2, y2 = BOARD_REGIONS[board_filename]
                board_center_x = (x1 + x2) // 2
                board_center_y = (y1 + y2) // 2
                board_width = x2 - x1
                board_height = y2 - y1
                board_class_id = CLASS_MAP['board']
                board_label = yolo_format(board_class_id, board_center_x, board_center_y, board_width, board_height, board_img.width, board_img.height)
                yolo_labels.append(board_label)

            for pos in placement_positions:  # 遍历每个棋子放置位置
                class_name = random.choice(list(piece_info.keys()))  # 随机选择一种棋子类型
                piece_path = random.choice(piece_info[class_name])  # 从该类型中随机选择一个棋子图片
                piece_img = Image.open(piece_path).convert("RGBA")  # 打开棋子图片并转换为RGBA格式
                center_x, center_y = pos  # 获取棋子放置的中心坐标

                if random.random() < 0.7:
                    pSize = random.randint(18, 40)
                    piece_img = piece_img.resize((pSize, pSize), Image.LANCZOS)
                else:
                    #如果board_img的高度小于BOARD_HEIGHT，则棋子缩放成47*47
                    if board_img.height < BOARD_HEIGHT:
                        piece_img = piece_img.resize((47, 47), Image.LANCZOS)
                            
                if random.random() < 0.5:
                    # piece_img 降低图片亮度
                    enhancer = ImageEnhance.Brightness(piece_img)
                    brightness_factor = random.uniform(0.4, 0.7)  # 随机选择亮度因子，0.3-0.8之间
                    piece_img = enhancer.enhance(brightness_factor)

                top_left_x = center_x - piece_img.width // 2  # 计算棋子左上角x坐标
                top_left_y = center_y - piece_img.height // 2  # 计算棋子左上角y坐标
                #如果board_img的高度小于BOARD_HEIGHT，则棋子缩放成47*47
                if top_left_y + piece_img.height > board_img.height:
                    continue
                if top_left_x + piece_img.width > board_img.width:
                    continue
                board_img.paste(piece_img, (top_left_x, top_left_y), piece_img)  # 将棋子粘贴到棋盘上
                
                #如果class_name不在CLASS_NAMES中，则跳过
                if class_name not in CLASS_NAMES:
                    continue

                #生成标注
                class_id = CLASS_MAP[class_name]  # 获取类别ID
                label_str = yolo_format(class_id, center_x, center_y, piece_img.width, piece_img.height, board_img.width, board_img.height)  # 生成YOLO格式标注
                yolo_labels.append(label_str)  # 将标注添加到标签列表

            final_image = board_img.convert('RGB')  # 将最终图片转换为RGB格式
            img_filename = f"{split}_{i}.jpg"  # 生成图片文件名
            label_filename = f"{split}_{i}.txt"  # 生成标签文件名

            img_path = os.path.join(OUTPUT_DIR, 'images', split, img_filename)  # 构建图片保存路径
            label_path = os.path.join(OUTPUT_DIR, 'labels', split, label_filename)  # 构建标签保存路径

            final_image.save(img_path)  # 保存生成的图片
            with open(label_path, 'w') as f:  # 打开标签文件进行写入
                f.writelines(yolo_labels)  # 写入所有YOLO标签
            
            if (i + 1) % 100 == 0:  # 每生成100张图片
                print(f"Generated {i + 1}/{num_images} images for {split} set.")  # 打印进度信息

    print("--- Dataset generation complete! ---")  # 打印数据集生成完成信息
    print(f"Class map: {CLASS_MAP}")  # 打印类别映射字典

def mkview():
    os.makedirs(os.path.join(OUTPUT_DIR, 'test'), exist_ok=True)
    #将val的图片和标签都复制到test目录
    for img in os.listdir(os.path.join(OUTPUT_DIR, 'images', 'val')):
        shutil.copy(os.path.join(OUTPUT_DIR, 'images', 'val', img), os.path.join(OUTPUT_DIR, 'test', img))
    for label in os.listdir(os.path.join(OUTPUT_DIR, 'labels', 'val')):
        shutil.copy(os.path.join(OUTPUT_DIR, 'labels', 'val', label), os.path.join(OUTPUT_DIR, 'test', label))

    shutil.copy('classes.txt', os.path.join(OUTPUT_DIR, 'test', 'classes.txt'))


if __name__ == '__main__':  # 判断是否为主程序入口
    create_dataset()  # 调用数据集创建函数
    mkview()