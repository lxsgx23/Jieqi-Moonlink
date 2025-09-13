import os
import random
from PIL import Image
import shutil

PIECES_DIR = "pieces"
BOARD_DIR = "board"
OUTPUT_DIR = "datasets"

BOARD_WIDTH, BOARD_HEIGHT = 628, 693
PIECE_WIDTH, PIECE_HEIGHT = 80, 80

BOARD_ITEM_WIDTH, BOARD_ITEM_HEIGHT = 558, 619

NUM_COLS = 9
NUM_ROWS = 10

NUM_TRAIN_IMAGES = 2000
NUM_VAL_IMAGES = 400

piece_types = ['P', 'R', 'K', 'N', 'C', 'A', 'B', 'X']
colors = ['r', 'b']
CLASS_NAMES = [f"{c}{p}" for c in colors for p in piece_types] + ['board']
CLASS_MAP = {name: i for i, name in enumerate(CLASS_NAMES)}

def get_grid_coordinates(board_width, board_height, num_cols, num_rows):
    """计算棋盘上所有交叉点的像素坐标"""
    coords = []
    margin_x = board_width * 0.05
    margin_y = board_height * 0.05
    grid_width = (board_width - 2 * margin_x) / (num_cols - 1)
    grid_height = (board_height - 2 * margin_y) / (num_rows - 1)

    for i in range(num_rows):
        for j in range(num_cols):
            x = int(margin_x + j * grid_width)
            y = int(margin_y + i * grid_height)
            coords.append((x, y))
    return coords

def yolo_format(class_id, center_x, center_y, width, height, image_width, image_height):

    x = center_x / image_width
    y = center_y / image_height
    w = width / image_width
    h = height / image_height
    return f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n"

def create_dataset():

    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    for split in ['train', 'val']:
        os.makedirs(os.path.join(OUTPUT_DIR, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, 'labels', split), exist_ok=True)

    board_files = [os.path.join(BOARD_DIR, f) for f in os.listdir(BOARD_DIR) if f.endswith('.png')]
    piece_files = [f for f in os.listdir(PIECES_DIR) if f.endswith('.png')]
    
    piece_info = {}
    for f in piece_files:
        color = f[0] # 'r' or 'b'
        piece_type = f[1] # 'P', 'R', etc.
        class_name = f"{color}{piece_type}"
        if class_name in piece_info:
            piece_info[class_name].append(os.path.join(PIECES_DIR, f))
        else:
            piece_info[class_name] = [os.path.join(PIECES_DIR, f)]

    grid_coords = get_grid_coordinates(BOARD_WIDTH, BOARD_HEIGHT, NUM_COLS, NUM_ROWS)

    board_item_center_x = BOARD_WIDTH // 2
    board_item_center_y = BOARD_HEIGHT // 2

    #生成图片和标注
    for split in ['train', 'val']:
        num_images = NUM_TRAIN_IMAGES if split == 'train' else NUM_VAL_IMAGES
        print(f"--- Generating {split} data ---")

        for i in range(num_images):

            board_path = random.choice(board_files)
            board_img = Image.open(board_path).convert("RGBA")
            num_pieces_to_place = random.randint(5, 32)
            
            random.shuffle(grid_coords)
            placement_positions = grid_coords[:num_pieces_to_place]
            
            yolo_labels = []

            board_class_id = CLASS_MAP['board']
            board_label_str = yolo_format(
                board_class_id, 
                board_item_center_x, 
                board_item_center_y, 
                BOARD_ITEM_WIDTH, 
                BOARD_ITEM_HEIGHT, 
                BOARD_WIDTH, 
                BOARD_HEIGHT
            )
            yolo_labels.append(board_label_str)

            for pos in placement_positions:
                class_name = random.choice(list(piece_info.keys()))
                piece_path = random.choice(piece_info[class_name])

                piece_img = Image.open(piece_path).convert("RGBA")
                center_x, center_y = pos
                top_left_x = center_x - PIECE_WIDTH // 2
                top_left_y = center_y - PIECE_HEIGHT // 2
                board_img.paste(piece_img, (top_left_x, top_left_y), piece_img)

                class_id = CLASS_MAP[class_name]
                label_str = yolo_format(class_id, center_x, center_y, PIECE_WIDTH, PIECE_HEIGHT, BOARD_WIDTH, BOARD_HEIGHT)
                yolo_labels.append(label_str)

            final_image = board_img.convert('RGB')
            img_filename = f"{split}_{i}.jpg"
            label_filename = f"{split}_{i}.txt"

            img_path = os.path.join(OUTPUT_DIR, 'images', split, img_filename)
            label_path = os.path.join(OUTPUT_DIR, 'labels', split, label_filename)

            final_image.save(img_path)
            with open(label_path, 'w') as f:
                f.writelines(yolo_labels)
            
            if (i + 1) % 100 == 0:
                print(f"Generated {i + 1}/{num_images} images for {split} set.")

    print("--- Dataset generation complete! ---")
    print(f"Class map: {CLASS_MAP}")

if __name__ == '__main__':
    create_dataset()