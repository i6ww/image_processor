import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import os
import tkinterdnd2 as tkdnd
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import queue
import sys #导入sys


# 获取资源路径的函数 (重要!)
def get_resource_path(relative_path):
    """
    获取资源的绝对路径 (支持源码模式和打包模式)
    """
    try:
        # PyInstaller 创建的临时文件夹
        base_path = sys._MEIPASS
    except Exception:
        # 正常模式 (源码模式)
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)



class ImageBatchProcessor:

    def __init__(self, master):
        self.master = master
        # self.master.geometry("750x550")

        # 变量初始化
        self.input_dir = ""
        self.output_dir = ""
        self.scale_factor = tk.DoubleVar(value=10.0)
        self.output_format = tk.StringVar(value="JPEG")
        self.output_width = tk.IntVar()
        self.output_height = tk.IntVar()
        self.resize_mode = tk.IntVar(value=1)

        # 日志记录器
        self.logger = self.setup_logger()

        # 创建一个队列用于线程间通信
        self.gui_queue = queue.Queue()

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=4)

        style = ttk.Style(self.master)
        style.configure("TButton", padding=6, relief="flat")
        style.configure("TEntry", padding=5)
        style.configure("TLabel", font=("Arial", 10))
        style.configure("TScale", background="lightgray")
        style.configure("Horizontal.TProgressbar", troughcolor='lightgray', background='green')

        self.create_widgets()
        self.master.after(100, self.process_gui_queue)


    def setup_logger(self):
        logger = logging.getLogger("ImageProcessor")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # 使用 get_resource_path 获取日志文件的路径
        log_file_path = get_resource_path("image_processor.log")
        fh = logging.FileHandler(log_file_path, mode='w')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        return logger

    def create_widgets(self):
        # 1. 文件选择
        input_frame = ttk.Frame(self.master)
        input_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(input_frame, text="输入文件夹:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.input_entry = ttk.Entry(input_frame, width=40)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5)
        self.input_entry.drop_target_register(tkdnd.DND_FILES)
        self.input_entry.dnd_bind('<<Drop>>', self.handle_drop)

        ttk.Button(input_frame, text="选择", command=self.select_input_dir).grid(row=0, column=2, pady=5)

        ttk.Label(input_frame, text="输出文件夹:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_entry = ttk.Entry(input_frame, width=40)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(input_frame, text="选择", command=self.select_output_dir).grid(row=1, column=2, pady=5)

        # 2. 尺寸调整
        size_frame = ttk.Frame(self.master)
        size_frame.pack(pady=10, padx=10, fill=tk.X)

        # 等比
        scale_frame = ttk.Frame(size_frame)
        scale_frame.pack(fill=tk.X)
        ttk.Radiobutton(scale_frame, text="等比缩放", variable=self.resize_mode, value=1).pack(side=tk.LEFT)
        self.scale_slider = ttk.Scale(scale_frame, from_=1, to=20, orient=tk.HORIZONTAL,
                                      variable=self.scale_factor)
        self.scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.scale_label = ttk.Label(scale_frame, text="100%")
        self.scale_label.pack(side=tk.LEFT)
        self.scale_slider.config(command=self.update_scale_label)

        # 指定尺寸
        dimension_frame = ttk.Frame(size_frame)
        dimension_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(dimension_frame, text="指定尺寸", variable=self.resize_mode, value=2).pack(side=tk.LEFT)

        ttk.Label(dimension_frame, text="宽度:").pack(side=tk.LEFT, padx=(10, 2))
        self.width_entry = ttk.Entry(dimension_frame, width=8, textvariable=self.output_width)
        self.width_entry.pack(side=tk.LEFT)
        ttk.Label(dimension_frame, text="px").pack(side=tk.LEFT, padx=5)

        ttk.Label(dimension_frame, text="高度:").pack(side=tk.LEFT)
        self.height_entry = ttk.Entry(dimension_frame, width=8, textvariable=self.output_height)
        self.height_entry.pack(side=tk.LEFT)
        ttk.Label(dimension_frame, text="px").pack(side=tk.LEFT, padx=5)

        # 3. 格式选择
        format_frame = ttk.Frame(self.master)
        format_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT)
        format_combo = ttk.Combobox(format_frame, values=["JPEG", "PNG", "GIF", "BMP", "TIFF"],
                                    textvariable=self.output_format, state="readonly")
        format_combo.pack(side=tk.LEFT, padx=5)
        format_combo.set("JPEG")

        # 4. 处理按钮和进度条
        button_frame = ttk.Frame(self.master)
        button_frame.pack(pady=20, padx=10)

        self.process_button = ttk.Button(button_frame, text="开始处理", command=self.process_images, width=15)
        self.process_button.pack()

        self.progress_bar = ttk.Progressbar(self.master, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

    def update_scale_label(self, *args):
        scale_value = self.scale_factor.get() / 10.0
        self.scale_label.config(text=f"{int(scale_value * 100)}%")

    def select_input_dir(self):
        self.input_dir = filedialog.askdirectory()
        self.input_entry.delete(0, tk.END)
        self.input_entry.insert(0, self.input_dir)


    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory()
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, self.output_dir)


    def handle_drop(self, event):
        path = event.data
        path = path.strip('{}')
        if os.path.isdir(path):
            self.input_dir = path
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, self.input_dir)
            self.logger.info(f"通过拖放设置输入文件夹: {path}")
        else:
            self.logger.warning("拖放的不是文件夹: %s", path)
            messagebox.showwarning("警告", "请拖放文件夹，而不是文件")


    def process_single_image(self, filename):
        self.logger.debug(f"线程 {os.getpid()}: 开始处理 {filename}")
        try:
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                return

            # 注意：这里不需要更改，因为输入和输出文件夹是用户选择的，
            #       在打包后通常也能正确处理。
            img_path = os.path.join(self.input_dir, filename)
            try:
                img = Image.open(img_path)
                self.logger.debug(f"  图像尺寸: {img.size}, 模式: {img.mode}, 格式: {img.format}")
            except Exception as e:
                self.logger.exception(f"  打开图像失败: {e}")
                self.gui_queue.put(("error", f"打开图像 {filename} 失败: {e}"))
                return

            scale = self.scale_factor.get() / 10.0
            output_format = self.output_format.get().lower()

            if self.resize_mode.get() == 1:
                width, height = img.size
                new_width = int(width * scale)
                new_height = int(height * scale)
            else:
                new_width = self.output_width.get()
                new_height = self.output_height.get()

            try:
                resized_img = img.resize((new_width, new_height))
            except Exception as e:
                self.logger.exception(f"  调整图像尺寸失败: {e}")
                self.gui_queue.put(("error", f"调整图像 {filename} 尺寸失败: {e}"))
                return

            output_filename = os.path.splitext(filename)[0] + "." + output_format

            # 注意: 这里也不需要改, 即使用户选择的输出目录是相对路径,
            #       打包后的程序通常也能工作 (除非用户把 exe 移动到其他位置).
            #       但为了更安全, 也可以考虑将输出目录转换为绝对路径.
            output_path = os.path.join(self.output_dir, output_filename)

            try:
                resized_img.save(output_path, format=output_format)
            except Exception as e:
                self.logger.exception(f"  保存图像失败: {e}")
                self.gui_queue.put(("error", f"保存图像 {filename} 失败: {e}"))
                return
            finally:
                if 'resized_img' in locals():
                    resized_img.close()
                img.close()

            self.gui_queue.put(("progress", 1))
            self.gui_queue.put(("log", f"已处理: {filename} -> {output_filename}"))

        except Exception as e:
            self.logger.exception(f"处理文件 {filename} 时发生未知错误: {e}")
            self.gui_queue.put(("error", f"处理文件 {filename} 时发生未知错误: {e}"))
        finally:
            self.logger.debug(f"线程 {os.getpid()}: 完成处理 {filename}")

    def process_images(self):
        if not self.input_dir or not self.output_dir:
            messagebox.showerror("错误", "请选择输入和输出文件夹")
            return

        if not os.path.isdir(self.input_dir) or not os.path.isdir(self.output_dir):
            messagebox.showerror("错误", "输入或输出文件夹不存在")
            return

        self.process_button.config(state=tk.DISABLED)

        try:
            image_files = [f for f in os.listdir(self.input_dir)
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'))]
            num_files = len(image_files)

            if num_files == 0:
                messagebox.showinfo("提示", "输入文件夹中没有找到支持的图像文件")
                self.process_button.config(state=tk.NORMAL)
                return

            self.progress_bar["maximum"] = num_files
            self.progress_bar["value"] = 0

            for filename in image_files:
                self.executor.submit(self.process_single_image, filename)

        except Exception as e:
            self.logger.exception(f"处理过程中发生错误: {e}")
            self.gui_queue.put(("error", "处理过程中发生错误，请查看日志"))
        finally:
            self.gui_queue.put(("done",))

    def process_gui_queue(self):
        try:
            while True:
                message = self.gui_queue.get_nowait()
                if message[0] == "progress":
                    self.progress_bar["value"] += message[1]
                elif message[0] == "log":
                    self.logger.info(message[1])
                elif message[0] == "error":
                    messagebox.showerror("错误", message[1])
                elif message[0] == "done":
                    messagebox.showinfo("完成", "图片处理完成/或出错!")
                    self.logger.info("所有图片处理完成/或出错")
                    self.process_button.config(state=tk.NORMAL)
                    self.progress_bar["value"] = 0

        except queue.Empty:
            pass
        finally:
            self.master.after(100, self.process_gui_queue)


if __name__ == "__main__":
    root = tkdnd.TkinterDnD.Tk()
    root.title("批量图片处理工具-韵网小工具")
    app = ImageBatchProcessor(root)
    root.mainloop()
