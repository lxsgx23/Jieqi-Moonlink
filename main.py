import os
import warnings
import sys
warnings.filterwarnings("ignore", category=UserWarning, message=".pkg_resources is deprecated.")
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import subprocess
import time
import numpy as np
import mss
from ultralytics import YOLO
import cv2
import win32gui
import win32api
import win32con
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import pyautogui

DEBUG_ENABLED = False

class NullWriter:
    """一个用于重定向流的空设备，它会忽略所有写入操作。"""
    def write(self, s):
        pass
    def flush(self):
        pass

def _d_print(*args, **kwargs):
    """全局打印函数，仅在DEBUG_ENABLED为True时输出到命令行。"""
    if DEBUG_ENABLED:
        print(*args, **kwargs)

BOARD_SIZE = (800, 850)
PIECE_SIZE = 64          # 棋子逻辑尺寸
GRID_SIZE = 600 // 9
BOARD_OFFSET = (5, 0)

SETTINGS_FILE = os.path.join('resource', 'settings.json')

def get_default_settings():
    return {
        "engine_threads": 8,
        "hash_size": 512,
        "engine_think_time": 2000,
        "board_scan_interval": 0.15,
        "board_click_interval": 0.50,
        "fixed_scan_interval": 1.0,
        "model_path": "resource/models/Moonlink_tiantian_wooden_v1.pt",
        "confidence_threshold": 0.90,
        "use_mouse_click": 0,
        "debug_mode": 0
    }

def load_settings():
    if not os.path.exists(os.path.dirname(SETTINGS_FILE)):
        os.makedirs(os.path.dirname(SETTINGS_FILE))
    if not os.path.exists(SETTINGS_FILE):
        settings = get_default_settings()
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        return settings
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            defaults = get_default_settings()
            for key, value in defaults.items():
                if key not in settings:
                    settings[key] = value
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        _d_print("警告: settings.json 读取失败，使用默认设置。")
        return get_default_settings()

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
    # 更新全局调试标志
    global DEBUG_ENABLED
    DEBUG_ENABLED = True if settings.get("debug_mode", 0) == 1 else False

def show_settings_window(current_settings):
    window = tk.Tk()
    window.title("设置")
    window.geometry("500x430")
    window.resizable(False, False)

    entries = {}
    options = {
        "engine_threads": "引擎线程:",
        "hash_size": "置换表大小 (MB):",
        "engine_think_time": "引擎思考时间 (ms):",
        "board_scan_interval": "棋盘识别间隔 (s):",
        "board_click_interval": "棋盘点击间隔 (s):",
        "fixed_scan_interval": "固定刷新识别间隔 (s):",
        "confidence_threshold": "置信度阈值 (0.0-1.0):",
        "use_mouse_click": "使用鼠标点击:",
        "debug_mode": "调试模式:",
        "model_path": "识别模型:"
    }

    for i, (key, label_text) in enumerate(options.items()):
        frame = tk.Frame(window)
        frame.pack(fill='x', padx=10, pady=5)
        
        label = tk.Label(frame, text=label_text, width=25, anchor='w')
        label.pack(side='left')
        
        entry = tk.Entry(frame)
        entry.pack(side='left', expand=True, fill='x')
        entry.insert(0, str(current_settings.get(key, '')))
        entries[key] = entry

        if key == "model_path":
            def browse_file(entry_widget=entry):
                filepath = filedialog.askopenfilename(filetypes=[("PyTorch Models", "*.pt")])
                if filepath:
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, filepath)
            
            browse_button = tk.Button(frame, text="...", command=browse_file, width=3)
            browse_button.pack(side='right')

    def on_save():
        try:
            new_settings = {
                "engine_threads": int(entries["engine_threads"].get()),
                "hash_size": int(entries["hash_size"].get()),
                "engine_think_time": int(entries["engine_think_time"].get()),
                "board_scan_interval": float(entries["board_scan_interval"].get()),
                "board_click_interval": float(entries["board_click_interval"].get()),
                "fixed_scan_interval": float(entries["fixed_scan_interval"].get()),
                "model_path": entries["model_path"].get(),
                "confidence_threshold": float(entries["confidence_threshold"].get()),
                "use_mouse_click": int(entries["use_mouse_click"].get()),
                "debug_mode": int(entries["debug_mode"].get())
            }
            save_settings(new_settings)
            messagebox.showinfo("成功", "设置已保存！部分设置将在程序重启后生效。")
            window.destroy()
        except ValueError:
            messagebox.showerror("错误", "输入无效，请确保数值格式正确。")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    button_frame = tk.Frame(window)
    button_frame.pack(pady=20)

    save_button = tk.Button(button_frame, text="保存", command=on_save, width=10)
    save_button.pack(side='left', padx=10)

    cancel_button = tk.Button(button_frame, text="取消", command=window.destroy, width=10)
    cancel_button.pack(side='left', padx=10)

    window.mainloop()

class EngineCommunicationError(Exception):
    pass

def get_main_window_handle(hwnd):
    """获取窗口的顶级父句柄"""
    while win32gui.GetParent(hwnd):
        hwnd = win32gui.GetParent(hwnd)
    return hwnd

def select_board_roi():
    """让用户通过截图和拖拽选择棋盘区域"""
    pygame.init()
    info = pygame.display.Info()
    screen_width, screen_height = info.current_w, info.current_h
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.NOFRAME | pygame.FULLSCREEN)
    
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        sct_img = sct.grab(monitor)
        frame = pygame.image.frombytes(sct_img.rgb, sct_img.size, "RGB")
    
    screen.blit(frame, (0, 0))
    
    try:
        font = pygame.font.SysFont('Microsoft YaHei', 24)
    except:
        font = pygame.font.SysFont('sans', 24)
        
    text = font.render('请拖动鼠标框选棋盘区域，按 回车键 确认，按 ESC 退出。', True, (50, 255, 50), (0, 0, 0))
    text_rect = text.get_rect(center=(screen_width // 2, 30))
    screen.blit(text, text_rect)
    pygame.display.flip()

    start_pos = None
    end_pos = None
    running = True
    rect = None

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and rect:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    rect = None
                    running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                start_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                end_pos = event.pos
                if start_pos:
                    x = min(start_pos[0], end_pos[0])
                    y = min(start_pos[1], end_pos[1])
                    width = abs(start_pos[0] - end_pos[0])
                    height = abs(start_pos[1] - end_pos[1])
                    rect = pygame.Rect(x, y, width, height)

        if start_pos and pygame.mouse.get_pressed()[0]:
            current_pos = pygame.mouse.get_pos()
            
            screen.blit(frame, (0, 0))
            screen.blit(text, text_rect)
            
            temp_rect = pygame.Rect(
                min(start_pos[0], current_pos[0]),
                min(start_pos[1], current_pos[1]),
                abs(start_pos[0] - current_pos[0]),
                abs(start_pos[1] - current_pos[1])
            )
            pygame.draw.rect(screen, (0, 255, 0), temp_rect, 3) 
            pygame.display.flip()

    pygame.quit()

    if rect:
        return {'top': rect.y, 'left': rect.x, 'width': rect.width, 'height': rect.height}
    else:
        _d_print("未选择任何区域，程序退出。")
        sys.exit()

class BoardDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(BOARD_SIZE)
        pygame.display.set_caption("Moonlink")
        self.piece_images = {}
        self.small_piece_images = {}
        self.board_img = None
        self.donate_img = None
        
        try:
            self.font = pygame.font.SysFont('Microsoft YaHei', 24)
            self.button_font = pygame.font.SysFont('Microsoft YaHei', 22)
            self.small_font = pygame.font.SysFont('Microsoft YaHei', 18)
        except:
            self.font = pygame.font.SysFont('sans', 24)
            self.button_font = pygame.font.SysFont('sans', 22)
            self.small_font = pygame.font.SysFont('sans', 18)


        self.engine_depth = ""
        self.engine_score = ""
        
        self.settings_button_rect = pygame.Rect(620, BOARD_SIZE[1] - 310, 160, 50)
        self.connect_button_rect = pygame.Rect(620, BOARD_SIZE[1] - 250, 160, 50)
        self.button_color = (0, 150, 0)
        self.settings_button_color = (0, 100, 150)
        self.button_text_color = (255, 255, 255)

        self.dark_piece_buttons = {}
        
        self.load_images()

    def load_images(self):
        """加载棋盘和棋子图片"""
        board_path = os.path.join('resource', 'pieces', 'board.PNG')
        original_board = pygame.image.load(board_path).convert()
        self.board_img = pygame.transform.scale(original_board, (600, 670))

        pieces = {
            'r': ['R', 'N', 'B', 'A', 'K', 'C', 'P', 'X'],
            'b': ['R', 'N', 'B', 'A', 'K', 'C', 'P', 'X']
        }
        for color_code, piece_list in pieces.items():
            for piece_code in piece_list:
                key = f"{color_code}{piece_code}"
                img_path = os.path.join('resource', 'pieces', f'{key}.PNG')
                piece_img = pygame.image.load(img_path).convert_alpha()
                # --- MODIFIED: 同时创建大尺寸和小尺寸的图片 ---
                self.piece_images[key] = pygame.transform.scale(piece_img, (PIECE_SIZE, PIECE_SIZE))
                self.small_piece_images[key] = pygame.transform.scale(piece_img, (32, 32))
                # --- END MODIFIED ---
                
        donate_path = os.path.join('resource', 'pieces', 'donate.jpg')
        original_donate_img = pygame.image.load(donate_path).convert()
        self.donate_img = pygame.transform.scale(original_donate_img, (180, 180))

    def update_engine_info(self, depth, score, score_type):
        """更新引擎分析信息"""
        if depth == "":
            self.engine_depth = ""
            self.engine_score = ""
            return

        self.engine_depth = str(depth)
        
        if score_type == 'mate':
            if score > 0:
                self.engine_score = f"杀棋 ({score}步)"
            else:
                self.engine_score = f"被杀 ({-score}步)"
        else:  # 'cp'
            score_in_pawns = score / 100.0
            self.engine_score = f"{score_in_pawns:+.2f}"

    def draw_dark_piece_library(self, dark_pieces):
        """在棋盘下方绘制暗子库及其控制按钮"""
        lib_rect = pygame.Rect(0, 670, 600, BOARD_SIZE[1] - 670)
        self.screen.fill((50, 50, 50), lib_rect)
        pygame.draw.line(self.screen, (100, 100, 100), (0, 670), (600, 670), 2)

        self.dark_piece_buttons.clear()

        piece_order = ['R', 'N', 'B', 'A', 'C', 'P']
        
        # 绘制红方暗子
        start_x_red = 20
        y_pos_red = 690
        for i, p_char in enumerate(piece_order):
            key = f"r{p_char}"
            count = dark_pieces.get(key, 0)
            img = self.small_piece_images.get(key)
            
            x_pos = start_x_red + i * 95
            if img:
                self.screen.blit(img, (x_pos, y_pos_red))

            # 绘制数量
            count_surf = self.small_font.render(f"x {count}", True, (255, 200, 200))
            self.screen.blit(count_surf, (x_pos + 40, y_pos_red + 8))

            # 绘制并记录按钮区域
            plus_rect = pygame.Rect(x_pos + 75, y_pos_red, 20, 15)
            minus_rect = pygame.Rect(x_pos + 75, y_pos_red + 17, 20, 15)
            pygame.draw.rect(self.screen, (0, 100, 0), plus_rect, border_radius=3)
            pygame.draw.rect(self.screen, (100, 0, 0), minus_rect, border_radius=3)
            plus_text = self.small_font.render("+", True, (255, 255, 255))
            minus_text = self.small_font.render("-", True, (255, 255, 255))
            self.screen.blit(plus_text, plus_text.get_rect(center=plus_rect.center))
            self.screen.blit(minus_text, minus_text.get_rect(center=minus_rect.center))

            self.dark_piece_buttons[(key, 'add')] = plus_rect
            self.dark_piece_buttons[(key, 'sub')] = minus_rect

        # 绘制黑方暗子
        start_x_black = 20
        y_pos_black = 755
        for i, p_char in enumerate(piece_order):
            key = f"b{p_char.upper()}"
            count = dark_pieces.get(key, 0)
            img = self.small_piece_images.get(key)
            
            x_pos = start_x_black + i * 95
            if img:
                self.screen.blit(img, (x_pos, y_pos_black))

            count_surf = self.small_font.render(f"x {count}", True, (200, 200, 255))
            self.screen.blit(count_surf, (x_pos + 40, y_pos_black + 8))
            
            plus_rect = pygame.Rect(x_pos + 75, y_pos_black, 20, 15)
            minus_rect = pygame.Rect(x_pos + 75, y_pos_black + 17, 20, 15)
            pygame.draw.rect(self.screen, (0, 100, 0), plus_rect, border_radius=3)
            pygame.draw.rect(self.screen, (100, 0, 0), minus_rect, border_radius=3)
            plus_text = self.small_font.render("+", True, (255, 255, 255))
            minus_text = self.small_font.render("-", True, (255, 255, 255))
            self.screen.blit(plus_text, plus_text.get_rect(center=plus_rect.center))
            self.screen.blit(minus_text, minus_text.get_rect(center=minus_rect.center))

            self.dark_piece_buttons[(key, 'add')] = plus_rect
            self.dark_piece_buttons[(key, 'sub')] = minus_rect

    def handle_dark_piece_library_click(self, pos, dark_pieces):
        """检查点击位置是否在暗子库按钮上，并更新暗子数量"""
        max_counts = {'R':2,'N':2,'B':2,'A':2,'C':2,'P':5}
        for (key, action), rect in self.dark_piece_buttons.items():
            if rect.collidepoint(pos):
                p_char = key[1]
                limit = max_counts[p_char]
                if action == 'add' and dark_pieces[key] < limit:
                    dark_pieces[key] += 1
                elif action == 'sub' and dark_pieces[key] > 0:
                    dark_pieces[key] -= 1
                return True
        return False

    def draw_captured_board(self, board_state, dark_pieces, is_running=False):
        """根据捕获到的board_state绘制棋盘、引擎信息、暗子库和控制按钮"""
        self.screen.fill((30, 30, 30))
        self.screen.blit(self.board_img, (0, 0))

        for row in range(10):
            for col in range(9):
                piece_name = board_state[row][col]
                if piece_name:
                    piece_img = self.piece_images.get(piece_name)
                    if piece_img:
                        x = BOARD_OFFSET[0] + col * GRID_SIZE
                        y = BOARD_OFFSET[1] + row * GRID_SIZE
                        piece_rect = piece_img.get_rect(center=(x + GRID_SIZE // 2, y + GRID_SIZE // 2))
                        self.screen.blit(piece_img, piece_rect)
        
        info_panel_rect = pygame.Rect(600, 0, 200, BOARD_SIZE[1])
        self.screen.fill((30, 30, 30), info_panel_rect)

        depth_label = self.font.render('引擎深度:', True, (200, 200, 200))
        depth_value = self.font.render(self.engine_depth, True, (50, 255, 50))
        self.screen.blit(depth_label, (620, 50))
        self.screen.blit(depth_value, (620, 80))

        score_label = self.font.render('局面评分:', True, (200, 200, 200))
        score_value = self.font.render(self.engine_score, True, (50, 255, 50))
        self.screen.blit(score_label, (620, 150))
        self.screen.blit(score_value, (620, 180))

        if self.donate_img:
            available_space_top = 210
            available_space_bottom = self.settings_button_rect.top
            center_y = available_space_top + (available_space_bottom - available_space_top) // 2
            donate_rect = self.donate_img.get_rect(center=(700, center_y))
            self.screen.blit(self.donate_img, donate_rect)

        pygame.draw.rect(self.screen, self.settings_button_color, self.settings_button_rect, border_radius=8)
        settings_text_surf = self.button_font.render("设置", True, self.button_text_color)
        settings_text_rect = settings_text_surf.get_rect(center=self.settings_button_rect.center)
        self.screen.blit(settings_text_surf, settings_text_rect)

        pygame.draw.rect(self.screen, self.button_color, self.connect_button_rect, border_radius=8)
        
        button_text_str = "重启" if is_running else "连线"
        button_text_surf = self.button_font.render(button_text_str, True, self.button_text_color)
        button_text_rect = button_text_surf.get_rect(center=self.connect_button_rect.center)
        self.screen.blit(button_text_surf, button_text_rect)
        
        self.draw_dark_piece_library(dark_pieces)
        pygame.display.flip()

class AutoChessPlayer:
    def __init__(self, roi):
        self.settings = load_settings()
        self.roi = roi
        try:
            self.yolo_model = YOLO(self.settings['model_path'])
            self.piece_names = self.yolo_model.names
        except Exception as e:
            _d_print(f"错误: 无法加载YOLO模型于路径 '{self.settings['model_path']}'. 错误: {e}")
            _d_print("请在设置中检查模型路径是否正确。程序将退出。")
            sys.exit(1)
        
        self.last_board_state = None
        self.computer_side = None # 'r' or 'b'
        
        self.hwnd = None

        self.current_player = 'r'
        self.game_over = False
        self.move_notations = []
        self.board_history = []
        
        self.game_state = "WAITING_FOR_NEW_GAME" 

        self.engine = None
        self.engine_path = os.path.join('resource', 'engine', 'engine.exe')
        
        self.initial_dark_pool = {
            'rR': 2, 'rN': 2, 'rB': 2, 'rA': 2, 'rC': 2, 'rP': 5,
            'bR': 2, 'bN': 2, 'bB': 2, 'bA': 2, 'bC': 2, 'bP': 5
        }
        self.dark_piece_library = self.initial_dark_pool.copy()
        
        try:
            self.init_engine()
        except EngineCommunicationError as e:
            _d_print(f"FATAL: 引擎初始化失败: {e}. 程序无法启动。")
            sys.exit(1)

        self.display = BoardDisplay()
        
        self.is_running = False

    def create_empty_board(self):
        return [['' for _ in range(9)] for _ in range(10)]

    def update_library_from_board(self, board_state):
        """根据当前棋盘上的明子来计算并更新暗子库"""
        pool = self.initial_dark_pool.copy()
        for r in range(10):
            for c in range(9):
                piece = board_state[r][c]
                # 只计算明子 (非X和K)
                if piece and 'X' not in piece and 'K' not in piece:
                    if piece in pool and pool[piece] > 0:
                        pool[piece] -= 1
        
        self.dark_piece_library = pool
        _d_print("暗子库已根据当前棋盘状态更新。")

    def _handle_piece_reveal(self, revealed_piece_key):
        """
        当一个暗子被翻开时，调用此函数来更新暗子库。
        :param revealed_piece_key: 被翻开棋子的字符串标识，例如 'rR', 'bN'。
        """
        if revealed_piece_key and revealed_piece_key in self.dark_piece_library:
            if self.dark_piece_library[revealed_piece_key] > 0:
                self.dark_piece_library[revealed_piece_key] -= 1
                _d_print(f"[暗子库更新] 棋子 '{revealed_piece_key}' 被翻开，剩余数量: {self.dark_piece_library[revealed_piece_key]}")
            else:
                _d_print(f"[警告] 尝试减少一个在暗子库中数量已为0的棋子: '{revealed_piece_key}'。这可能表示之前的识别有误。")

    def init_engine(self):
        """
        初始化或重新初始化UCI引擎。如果已存在引擎进程，会尝试终止它。
        """
        if self.engine:
            _d_print("正在终止现有引擎进程以进行重新初始化...")
            try:
                self.send_engine_command("quit")
                self.engine.wait(timeout=1)
            except (EngineCommunicationError, subprocess.TimeoutExpired):
                pass
            except Exception as e:
                _d_print(f"终止现有引擎时发生未知错误: {e}")
            if self.engine.poll() is None:
                _d_print("强制终止旧引擎进程。")
                self.engine.terminate()
            self.engine = None

        _d_print("正在启动新的引擎进程...")
        try:
            self.engine = subprocess.Popen(
                self.engine_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.send_engine_command("uci")
            self.send_engine_command(f"setoption name Threads value {self.settings['engine_threads']}")
            self.send_engine_command(f"setoption name Hash value {self.settings['hash_size']}")
            self.send_engine_command("isready")
            
            ready_timeout = 10
            start_time = time.time()
            while time.time() - start_time < ready_timeout:
                output = self.read_engine_output()
                if "readyok" in output:
                    _d_print("引擎已准备就绪。")
                    return
                time.sleep(0.1)
            
            raise EngineCommunicationError("引擎未能在规定时间内响应'readyok'。")

        except EngineCommunicationError:
            if self.engine: self.engine.terminate()
            self.engine = None
            raise
        except FileNotFoundError:
            if self.engine: self.engine.terminate()
            self.engine = None
            raise EngineCommunicationError(f"引擎文件未找到: {self.engine_path}")
        except Exception as e:
            if self.engine: self.engine.terminate()
            self.engine = None
            raise EngineCommunicationError(f"通用引擎启动错误: {e}")

    def send_engine_command(self, command):
        """
        向UCI引擎发送命令。
        """
        if self.engine and self.engine.stdin:
            _d_print(f"To Engine: {command}")
            try:
                self.engine.stdin.write(command + "\n")
                self.engine.stdin.flush()
            except OSError as e:
                _d_print(f"ERROR: 无法向引擎发送命令 '{command}'。错误: {e}")
                if self.engine: self.engine.terminate()
                self.engine = None
                raise EngineCommunicationError(f"引擎通信失败 (stdin不可用): {e}")
        elif self.engine is None:
            raise EngineCommunicationError("引擎未初始化或已失效。")
        else:
            if self.engine: self.engine.terminate()
            self.engine = None
            raise EngineCommunicationError("引擎stdin不可用。")

    def read_engine_output(self):
        """从引擎读取一行输出"""
        if self.engine and self.engine.stdout:
            return self.engine.stdout.readline().strip()
        return ""

    def find_game_window(self):
        """
        根据ROI区域的左上角坐标找到游戏窗口的句柄。
        """
        try:
            point = (self.roi['left'], self.roi['top'])
            hwnd_child = win32gui.WindowFromPoint(point)
            
            if hwnd_child == 0:
                _d_print(f"错误：在坐标 {point} 处未找到窗口。请确保ROI完全在游戏窗口内。")
                return False
            
            self.hwnd = get_main_window_handle(hwnd_child)
            
            window_text = win32gui.GetWindowText(self.hwnd)
            _d_print(f"成功绑定到游戏窗口：句柄={self.hwnd}, 标题='{window_text}'")
            return True
        except Exception as e:
            _d_print(f"查找窗口句柄时发生错误: {e}")
            self.hwnd = None
            return False

    def _capture_single_frame(self):
        """
        执行一次屏幕捕获和YOLO识别，返回单次的棋盘状态。
        """
        with mss.mss() as sct:
            screenshot = sct.grab(self.roi)
            img = np.array(screenshot)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        results = self.yolo_model(img_bgr, verbose=False)
        
        board_state = self.create_empty_board()
        grid_h = self.roi['height'] / 10
        grid_w = self.roi['width'] / 9

        for res in results:
            for box in res.boxes:
                if box.conf[0] > self.settings['confidence_threshold']:
                    x1, y1, x2, y2 = box.xyxy[0]
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    row = int(center_y / grid_h)
                    col = int(center_x / grid_w)
                    if 0 <= row < 10 and 0 <= col < 9:
                        piece_id = int(box.cls[0])
                        board_state[row][col] = self.piece_names[piece_id]
        return board_state

    def get_board_state_from_screen(self, max_retries=10):
        """
        通过连续两次识别结果是否一致来确保捕获的是静止的棋盘状态。
        """
        delay = self.settings['board_scan_interval']
        board1 = self._capture_single_frame()
        for _ in range(max_retries):
            time.sleep(delay)
            board2 = self._capture_single_frame()
            if board1 == board2:
                return board2
        board1 = board2
        
        _d_print("\n警告: 棋盘状态在多次尝试后仍未稳定，可能导致识别错误。")
        return board1

    def compare_boards(self, old_board, new_board):
        """比较两个棋盘状态，推断出发生的移动"""
        disappeared, appeared = [], []
        for r in range(10):
            for c in range(9):
                if old_board[r][c] != new_board[r][c]:
                    if old_board[r][c] and not new_board[r][c]:
                        disappeared.append({'pos': (r, c), 'piece': old_board[r][c]})
                    elif not old_board[r][c] and new_board[r][c]:
                        appeared.append({'pos': (r, c), 'piece': new_board[r][c]})
                    else:
                        disappeared.append({'pos': (r, c), 'piece': old_board[r][c]})
                        appeared.append({'pos': (r, c), 'piece': new_board[r][c]})

        if len(disappeared) == 1 and len(appeared) == 1 and disappeared[0]['pos'] == appeared[0]['pos']:
            from_pos = disappeared[0]['pos']
            old_piece = disappeared[0]['piece']
            new_piece = appeared[0]['piece']
            revealed_char = ''
            if 'X' in old_piece:
                revealed_char = new_piece[1]
                if new_piece[0] == 'b':
                    revealed_char = revealed_char.lower()
            return (from_pos[0], from_pos[1], from_pos[0], from_pos[1], revealed_char)
        
        if len(appeared) == 1 and (len(disappeared) in [1, 2]):
            to_pos = appeared[0]['pos']
            appeared_piece = appeared[0]['piece']
            from_pos = None
            mover_piece_info = None

            for item in disappeared:
                if item['piece'][0] == appeared_piece[0] and item['pos'] != to_pos:
                    from_pos = item['pos']
                    mover_piece_info = item
                    break
            
            if from_pos is None:
                for item in disappeared:
                    if 'X' in item['piece']:
                        from_pos = item['pos']
                        mover_piece_info = item
                        break

            if from_pos is None: return None

            revealed_char = ''
            if mover_piece_info and 'X' in mover_piece_info['piece']:
                revealed_char = appeared_piece[1]
                if appeared_piece[0] == 'b':
                    revealed_char = revealed_char.lower()
            return (from_pos[0], from_pos[1], to_pos[0], to_pos[1], revealed_char)
        
        return None

    def move_to_uci(self, from_row, from_col, to_row, to_col, revealed_piece=''):
        """将棋盘坐标转换为UCI移动字符串"""
        col_map = "abcdefghi"
        if self.computer_side == 'b':
            from_sq = f"{col_map[8 - from_col]}{from_row}"
            to_sq = f"{col_map[8 - to_col]}{to_row}"
        else:
            from_sq = f"{col_map[from_col]}{9 - from_row}"
            to_sq = f"{col_map[to_col]}{9 - to_row}"
        return f"{from_sq}{to_sq}{revealed_piece}"

    def uci_to_board_coords(self, uci_move):
        """将UCI移动字符串转换为棋盘坐标"""
        col_map = "abcdefghi"
        from_col_engine = col_map.index(uci_move[0])
        from_row_engine = int(uci_move[1])
        to_col_engine = col_map.index(uci_move[2])
        to_row_engine = int(uci_move[3])
        if self.computer_side == 'b':
            from_col, from_row = 8 - from_col_engine, from_row_engine
            to_col, to_row = 8 - to_col_engine, to_row_engine
        else:
            from_col, from_row = from_col_engine, 9 - from_row_engine
            to_col, to_row = to_col_engine, 9 - to_row_engine
        return (from_row, from_col, to_row, to_col)

    def grid_to_screen_coords(self, row, col):
        """将棋盘格子坐标转换为绝对屏幕坐标"""
        grid_h = self.roi['height'] / 10
        grid_w = self.roi['width'] / 9
        screen_x = self.roi['left'] + (col * grid_w) + (grid_w / 2)
        screen_y = self.roi['top'] + (row * grid_h) + (grid_h / 2)
        return screen_x, screen_y

    def perform_move_on_screen(self, uci_move):
        """根据设置选择并执行走棋方法"""
        if self.settings.get('use_mouse_click', 0) == 1:
            self.simulate_move_with_autogui(uci_move)
        else:
            self.simulate_move_with_postmessage(uci_move)
            
    def simulate_move_with_autogui(self, uci_move):
        """使用 pyautogui 模拟鼠标点击来执行走棋"""
        if len(uci_move) < 4: return

        from_row, from_col, to_row, to_col = self.uci_to_board_coords(uci_move)
        start_screen_x, start_screen_y = self.grid_to_screen_coords(from_row, from_col)
        end_screen_x, end_screen_y = self.grid_to_screen_coords(to_row, to_col)

        _d_print(f"执行鼠标点击: {uci_move} 从 ({int(start_screen_x)}, {int(start_screen_y)}) 到 ({int(end_screen_x)}, {int(end_screen_y)}) (屏幕坐标)")

        pyautogui.click(x=start_screen_x, y=start_screen_y)
        time.sleep(self.settings['board_click_interval'])
        pyautogui.click(x=end_screen_x, y=end_screen_y)

    def simulate_move_with_postmessage(self, uci_move):
        """使用 PostMessage 发送后台点击消息来执行走棋"""
        if len(uci_move) < 4: return
        if not self.hwnd:
            _d_print("错误：未找到有效的游戏窗口句柄，无法执行走子。")
            return

        from_row, from_col, to_row, to_col = self.uci_to_board_coords(uci_move)
        start_screen_pos = self.grid_to_screen_coords(from_row, from_col)
        end_screen_pos = self.grid_to_screen_coords(to_row, to_col)
        start_client_pos = win32gui.ScreenToClient(self.hwnd, (int(start_screen_pos[0]), int(start_screen_pos[1])))
        end_client_pos = win32gui.ScreenToClient(self.hwnd, (int(end_screen_pos[0]), int(end_screen_pos[1])))
        start_lParam = win32api.MAKELONG(start_client_pos[0], start_client_pos[1])
        end_lParam = win32api.MAKELONG(end_client_pos[0], end_client_pos[1])

        _d_print(f"发送后台点击: {uci_move} 从 {start_client_pos} 到 {end_client_pos} (窗口坐标)")
        
        win32api.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, start_lParam)
        time.sleep(0.05)
        win32api.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, start_lParam)
        
        time.sleep(self.settings['board_click_interval'])
        
        win32api.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, end_lParam)
        time.sleep(0.05)
        win32api.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, end_lParam)

    def is_board_state_valid(self, board_state):
        """验证棋盘状态是否合法"""
        piece_counts = {p: 0 for p in ['rK','rA','rB','rN','rR','rC','rP','bK','bA','bB','bN','bR','bC','bP']}
        max_counts = {'rK':1,'rA':2,'rB':2,'rN':2,'rR':2,'rC':2,'rP':5,'bK':1,'bA':2,'bB':2,'bN':2,'bR':2,'bC':2,'bP':5}
        red_king_pos, black_king_pos = None, None

        for r in range(10):
            for c in range(9):
                piece = board_state[r][c]
                if piece and 'X' not in piece:
                    if piece in piece_counts: piece_counts[piece] += 1
                    if piece == 'rK': red_king_pos = (r, c)
                    elif piece == 'bK': black_king_pos = (r, c)

        for piece, count in piece_counts.items():
            if count > max_counts[piece]:
                _d_print(f"\n[Validation Error] 非法棋子数量: {piece}. 发现 {count}, 最大允许 {max_counts[piece]}.")
                self.reset_game()
                return False

        if red_king_pos and not (7<=red_king_pos[0]<=9 and 3<=red_king_pos[1]<=5 or 0<=red_king_pos[0]<=2 and 3<=red_king_pos[1]<=5):
            _d_print(f"\n[Validation Error] 红帅位置非法: {red_king_pos}.")
            return False
        if black_king_pos and not (0<=black_king_pos[0]<=2 and 3<=black_king_pos[1]<=5 or 7<=black_king_pos[0]<=9 and 3<=black_king_pos[1]<=5):
            _d_print(f"\n[Validation Error] 黑将位置非法: {black_king_pos}.")
            return False
        if sum(piece_counts.values()) > 2 and (not red_king_pos or not black_king_pos):
            _d_print("\n[Validation Error] 棋盘上缺少将/帅。")
            return False
        return True
        
    def board_state_to_jieqi_fen(self, board_state):
        """将棋盘状态转换为揭棋FEN字符串"""
        if not board_state: return ""
        board_to_process = board_state
        if self.computer_side == 'b':
            flipped_rows = board_state[::-1]
            board_to_process = [row[::-1] for row in flipped_rows]

        fen_parts = []
        for r in range(10):
            empty_count = 0
            row_str = ''
            for c in range(9):
                piece = board_to_process[r][c]
                if not piece:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    p_char = piece[1]
                    if 'X' in p_char: p_char = 'x'
                    row_str += p_char.upper() if piece[0] == 'r' else p_char.lower()
            if empty_count > 0: row_str += str(empty_count)
            fen_parts.append(row_str)
        board_fen = "/".join(fen_parts)

        pool_str = ""
        fen_order = ['R','r','N','n','B','b','A','a','C','c','P','p']
        
        internal_to_fen = {
            'rR':'R', 'bR':'r', 'rN':'N', 'bN':'n', 'rB':'B', 'bB':'b',
            'rA':'A', 'bA':'a', 'rC':'C', 'bC':'c', 'rP':'P', 'bP':'p'
        }
        fen_to_internal = {v: k for k, v in internal_to_fen.items()}

        for p_char in fen_order:
            internal_key = fen_to_internal[p_char]
            count = self.dark_piece_library.get(internal_key, 0)
            if count > 0:
                pool_str += f"{p_char}{count}"
        
        player_turn = 'w' if self.current_player == 'r' else 'b'
        full_fen = f"{board_fen} {player_turn} {pool_str} 0 1"
        return full_fen

    def get_engine_move(self):
        """从引擎获取最佳走法"""
        movetime = self.settings['engine_think_time']
        current_fen = self.board_state_to_jieqi_fen(self.last_board_state)
        if not current_fen:
            _d_print("错误：无法生成当前局面的FEN，无法获取引擎走法。")
            return None
        
        position_cmd = f"position fen {current_fen}"
        _d_print(f"为引擎生成了新的FEN: {current_fen}")
        
        try:
            self.send_engine_command(position_cmd)
            self.send_engine_command(f"go movetime {movetime}")
        except EngineCommunicationError:
            _d_print("ERROR: 无法向引擎发送 'position' 或 'go' 命令。")
            raise

        bestmove = None
        timeout = (movetime / 1000) + 5.0
        start_time = time.time()
        _d_print("正在等待引擎计算最佳走法...")

        while time.time() - start_time < timeout:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.game_over = True
                    return None
            if self.game_over: break
            
            output = self.read_engine_output()
            if output.startswith("info"):
                parts = output.split()
                try:
                    depth, score_val, score_type = None, None, None
                    if "depth" in parts: depth = int(parts[parts.index("depth") + 1])
                    if "score" in parts:
                        score_idx = parts.index("score")
                        score_type = parts[score_idx + 1]
                        score_val = int(parts[score_idx + 2])
                    if depth and score_type and score_val is not None:
                        self.display.update_engine_info(depth, score_val, score_type)
                        self.display.draw_captured_board(self.last_board_state, self.dark_piece_library, self.is_running)
                except (ValueError, IndexError): pass

            elif output.startswith("bestmove"):
                bestmove = output.split(" ")[1]
                _d_print(f"引擎已找到最佳走法: {bestmove}")
                self.display.update_engine_info("", "", "")
                self.display.draw_captured_board(self.last_board_state, self.dark_piece_library, self.is_running)
                break
            elif not output and self.engine and self.engine.poll() is not None:
                self.engine = None
                raise EngineCommunicationError("引擎在计算最佳走法时意外终止。")
            elif not output:
                 time.sleep(0.01)

        if bestmove is None:
            if self.engine and self.engine.poll() is not None:
                self.engine = None
                raise EngineCommunicationError("引擎超时未返回最佳走法，且已终止。")
            raise EngineCommunicationError("引擎超时未返回最佳走法。")

        return bestmove

    def reset_game(self):
        """重置游戏变量并准备等待新游戏。"""
        _d_print("\n游戏结束或检测到错误。正在重置并等待新游戏...")
        self.move_notations.clear()
        self.current_player, self.computer_side = 'r', None
        self.last_board_state = None
        self.board_history.clear()
        self.game_state = "WAITING_FOR_NEW_GAME"
        self.display.update_engine_info("", "", "")
        
        self.dark_piece_library = self.initial_dark_pool.copy()
        _d_print("暗子库已重置为初始状态。")
        
        ready_timeout = 5
        try:
            self.send_engine_command("ucinewgame")
            self.send_engine_command("isready")
            start_time = time.time()
            while "readyok" not in self.read_engine_output():
                if time.time() - start_time > ready_timeout:
                    raise EngineCommunicationError("引擎在ucinewgame后未准备就绪。")
                time.sleep(0.1)
        except EngineCommunicationError as e:
            _d_print(f"引擎通信错误: {e}，尝试重新初始化引擎。")
            try:
                self.init_engine()
                _d_print("引擎重新初始化成功。")
            except EngineCommunicationError as re_init_e:
                _d_print(f"FATAL: 引擎重新初始化失败: {re_init_e}。")
                self.game_over = True
                return
            
        _d_print("游戏状态重置完成。现在等待新游戏。")

    def run(self):
        """主循环"""
        while not self.game_over:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.game_over = True
                    break
                if event.type == pygame.MOUSEBUTTONDOWN:

                    if self.display.handle_dark_piece_library_click(event.pos, self.dark_piece_library):
                        _d_print(f"手动调整暗子库: {self.dark_piece_library}")
                        pass

                    elif self.display.settings_button_rect.collidepoint(event.pos):
                        _d_print("\n[界面操作] “设置”按钮被按下。")
                        self.settings = load_settings()
                        show_settings_window(self.settings)
                        self.settings = load_settings()
                        _d_print("设置窗口已关闭。")

                    elif self.display.connect_button_rect.collidepoint(event.pos):
                        if self.is_running:
                            _d_print("\n[界面操作] “重启”按钮被按下。正在重置游戏状态...")
                            self.is_running = False
                            try: self.reset_game()
                            except EngineCommunicationError:
                                _d_print("错误：无法重启游戏，引擎通信失败。程序将退出。")
                                self.game_over = True
                        else:
                            _d_print("\n[界面操作] “连线”按钮被按下。正在启动自动对弈...")
                            self.is_running = True
                            try: self.reset_game()
                            except EngineCommunicationError:
                                _d_print("错误：无法启动游戏，引擎通信失败。程序将退出。")
                                self.game_over = True
            if self.game_over: break

            if self.is_running:
                try:
                    if self.game_state == "WAITING_FOR_NEW_GAME":
                        _d_print("\r正在搜索新的、合法的游戏棋盘...", end="", flush=True)
                        current_board = self.get_board_state_from_screen()
                        # 在等待时，也保持界面上的暗子库显示为最新状态
                        if self.last_board_state is None:
                            self.display.draw_captured_board(current_board, self.dark_piece_library, self.is_running)

                        if self.is_board_state_valid(current_board):
                            dark_piece_count = sum(1 for r in current_board for p in r if p and 'X' in p)
                            side_determined = False
                            
                            found_red_king_at_bottom = any(current_board[r][c] == 'rK' for r in range(7, 10) for c in range(3, 6))
                            found_black_king_at_bottom = any(current_board[r][c] == 'bK' for r in range(7, 10) for c in range(3, 6))
                            
                            if found_red_king_at_bottom:
                                self.computer_side, side_determined = 'r', True
                                _d_print("\n执棋方已确定: 电脑执红 (将帅在底部)。")
                            elif found_black_king_at_bottom:
                                self.computer_side, side_determined = 'b', True
                                _d_print("\n执棋方已确定: 电脑执黑 (将帅在底部，棋盘已翻转)。")
                            elif dark_piece_count == 32:
                                self.computer_side, side_determined = 'r', True
                                _d_print("\n检测到所有棋子面朝下。默认为电脑执红。")
                            
                            if side_determined:
                                # --- NEW: 根据识别到的棋盘，计算并设置初始暗子库 ---
                                self.update_library_from_board(current_board)
                                # --- END NEW ---

                                self.last_board_state = current_board
                                self.board_history.append(current_board)
                                self.current_player = 'r'
                                
                                if self.computer_side == 'b':
                                    self.game_state = "HYPOTHESIZE_BLACK_TURN"
                                    _d_print("检测到执黑方，进入先手假设模式。")
                                else:
                                    self.game_state = "PLAYING"
                                    _d_print("新游戏开始。进入对战模式。")
                        time.sleep(2)

                    elif self.game_state == "HYPOTHESIZE_BLACK_TURN":
                        _d_print("\n[执黑方] 检测到新局面，假设对手已走，尝试我方先行...")
                        
                        # 在黑方假设先行时，需要临时将走棋方设置为 'b' 来生成正确的FEN
                        original_player = self.current_player
                        self.current_player = 'b'
                        engine_move = self.get_engine_move()
                        self.current_player = original_player # 恢复

                        if not engine_move or engine_move == "(none)":
                            self.game_state = "PLAYING"
                            continue

                        board_before_move = self.last_board_state
                        self.perform_move_on_screen(engine_move)
                        
                        start_time = time.time()
                        while time.time() - start_time < 4.0:
                            current_board = self.get_board_state_from_screen()
                            if current_board != board_before_move:
                                move_tuple = self.compare_boards(board_before_move, current_board)
                                if move_tuple:
                                    detected_uci_move = self.move_to_uci(*move_tuple)
                                    # --- LOGIC CHANGE START ---
                                    # 如果检测到翻子，立即更新暗子库
                                    if move_tuple[4]:
                                        revealed_piece_pos = (move_tuple[2], move_tuple[3])
                                        piece_key = current_board[revealed_piece_pos[0]][revealed_piece_pos[1]]
                                        self._handle_piece_reveal(piece_key)
                                    # --- LOGIC CHANGE END ---
                                    
                                    self.move_notations.append(detected_uci_move)
                                    self.last_board_state = current_board
                                    self.board_history.append(current_board)
                                    
                                    # 判断是我方走棋成功还是对方抢先了
                                    if detected_uci_move[:4] == engine_move[:4]:
                                        _d_print(f"假设成功！我方走法 {detected_uci_move} 已确认。")
                                        self.current_player = 'r'
                                    else:
                                        _d_print(f"假设失败！对手抢先移动: {detected_uci_move}")
                                        self.current_player = 'b' # 对手走了，轮到我了
                                    
                                    break
                            time.sleep(0.1)
                        
                        self.game_state = "PLAYING"


                    elif self.game_state == "PLAYING":
                        if self.current_player == self.computer_side:
                            _d_print("\n--- 电脑回合 ---")
                            engine_move = self.get_engine_move()
                            if not engine_move or engine_move == "(none)":
                                self.reset_game(); continue
                            
                            board_before_move = self.last_board_state
                            self.perform_move_on_screen(engine_move)
                            
                            # 确认我方走棋是否成功
                            board_after_our_move = None
                            start_time = time.time()
                            time.sleep(self.settings['board_click_interval']) # 等待点击生效
                            while time.time() - start_time < 5.0:
                                snapshot = self.get_board_state_from_screen()
                                if snapshot != board_before_move:
                                    move_tuple = self.compare_boards(board_before_move, snapshot)
                                    if move_tuple:
                                        # --- LOGIC CHANGE START ---
                                        # 如果我方走法是翻子，则更新暗子库
                                        if move_tuple[4]:
                                            revealed_pos = (move_tuple[2], move_tuple[3])
                                            piece_key = snapshot[revealed_pos[0]][revealed_pos[1]]
                                            self._handle_piece_reveal(piece_key)
                                        # --- LOGIC CHANGE END ---
                                        
                                        corrected_uci_move = self.move_to_uci(*move_tuple)
                                        board_after_our_move = snapshot
                                        _d_print(f"最终确认我方走法: {corrected_uci_move}")
                                        self.move_notations.append(corrected_uci_move)
                                        break
                                time.sleep(0.1)

                            if board_after_our_move:
                                self.display.draw_captured_board(board_after_our_move, self.dark_piece_library, self.is_running)
                                self.last_board_state = board_after_our_move
                                self.board_history.append(board_after_our_move)
                                self.current_player = 'b' if self.current_player == 'r' else 'r'
                            else:
                                _d_print("错误：未能确认我方走法。尝试重置游戏。")
                                self.reset_game()
                        else: 
                            _d_print("\r--- 对手回合: 监控中 ---", end="", flush=True)
                            new_board_state = self.get_board_state_from_screen()
                            
                            if new_board_state != self.last_board_state:
                                _d_print() # 换行
                                if not self.is_board_state_valid(new_board_state):
                                    time.sleep(1)
                                    continue
                                    
                                move = self.compare_boards(self.last_board_state, new_board_state)
                                if move:
                                    # 如果对手的走法是翻子，则更新暗子库
                                    if move[4]:
                                        revealed_pos = (move[2], move[3])
                                        piece_key = new_board_state[revealed_pos[0]][revealed_pos[1]]
                                        self._handle_piece_reveal(piece_key)
                                    
                                    uci_move = self.move_to_uci(*move)
                                    _d_print(f"检测到对手走法: {uci_move}")
                                    self.move_notations.append(uci_move)
                                    self.last_board_state = new_board_state
                                    self.board_history.append(new_board_state)
                                    self.current_player = 'b' if self.current_player == 'r' else 'r'
                                else: 
                                    _d_print("\n检测到无法识别的棋盘变化，尝试重置游戏。")
                                    self.last_board_state = new_board_state # 更新状态以避免循环重置
                                    self.reset_game()
                            
                            # 界面实时更新，即使棋盘没变化
                            self.display.draw_captured_board(new_board_state, self.dark_piece_library, self.is_running)
                            time.sleep(self.settings['fixed_scan_interval'])

                except EngineCommunicationError as e:
                    _d_print(f"\n[错误] 引擎通信失败: {e}。")
                    self.reset_game()
                    if self.game_over: break
                except Exception as e:
                    _d_print(f"\n在对战中发生错误: {e}。尝试重置。")
                    self.reset_game()
            
            else:
                current_board = self._capture_single_frame()
                self.display.draw_captured_board(current_board, self.dark_piece_library, self.is_running)
                time.sleep(0.1)

        if self.engine:
            try: self.send_engine_command("quit")
            except EngineCommunicationError: pass
            finally:
                if self.engine and self.engine.poll() is None:
                    self.engine.terminate()
    
        pygame.quit()
        _d_print("引擎已关闭。程序退出。")

if __name__ == "__main__":

    settings = load_settings()
    if settings.get("debug_mode", 0) == 1:
        DEBUG_ENABLED = True
    else:
        # 如果关闭调试模式，将标准错误流重定向到空设备以抑制所有错误消息
        sys.stderr = NullWriter()

    try:
        roi = select_board_roi()
        if roi:
            _d_print(f"棋盘区域已选定: {roi}")
            player = AutoChessPlayer(roi)
            
            if not player.find_game_window():
                 _d_print("\n未能找到有效的游戏窗口句柄，程序即将退出。")
                 sys.exit(1)
                 
            player.run()
    except Exception as e:
        # 捕获所有未处理的异常，仅在调试模式下打印
        _d_print(f"程序发生错误: {e}")
        sys.exit(1)