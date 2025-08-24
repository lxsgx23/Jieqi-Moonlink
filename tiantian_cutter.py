import os
from PIL import Image

def process_images():
    # 创建输出目录
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 定义命名规则
    top_row_names = ['rP', 'rC', 'rN', 'rR', 'rB', 'rA', 'rK', 'rX', 'waste']
    bottom_row_names = ['bP', 'bC', 'bN', 'bR', 'bB', 'bA', 'bK', 'bX', 'blank']
    
    # 处理每张图片
    for i in range(1, 19):
        input_filename = f'{i}.png'
        
        # 检查文件是否存在
        if not os.path.exists(input_filename):
            print(f"警告: 文件 {input_filename} 不存在，跳过处理")
            continue
            
        try:
            # 打开图片
            img = Image.open(input_filename)
            
            # 验证图片尺寸
            if img.size != (720, 160):
                print(f"警告: 图片 {input_filename} 的尺寸不是720x160，实际尺寸为 {img.size}")
                continue
            
            # 裁剪并保存上面一行的9张小图片
            for col, name_prefix in enumerate(top_row_names):
                left = col * 80
                top = 0
                right = left + 80
                bottom = top + 80
                
                # 裁剪
                cropped_img = img.crop((left, top, right, bottom))
                
                # 保存
                output_filename = f'{name_prefix}{i}.png'
                output_path = os.path.join(output_dir, output_filename)
                cropped_img.save(output_path)
                print(f"已保存: {output_path}")
            
            # 裁剪并保存下面一行的9张小图片
            for col, name_prefix in enumerate(bottom_row_names):
                left = col * 80
                top = 80
                right = left + 80
                bottom = top + 80
                
                # 裁剪
                cropped_img = img.crop((left, top, right, bottom))
                
                # 保存
                output_filename = f'{name_prefix}{i}.png'
                output_path = os.path.join(output_dir, output_filename)
                cropped_img.save(output_path)
                print(f"已保存: {output_path}")
                
            print(f"已完成处理: {input_filename}")
            
        except Exception as e:
            print(f"处理图片 {input_filename} 时出错: {str(e)}")
    
    print("所有图片处理完成!")

if __name__ == "__main__":
    process_images()