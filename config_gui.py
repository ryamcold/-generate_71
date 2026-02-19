import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

CONFIG_FILE = "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "rotation_speed_drums": 0.1,
    "rotation_speed_bass": 0.1,
    "rotation_speed_other": 0.1,
    "rotate_vocals": False,
    "vocal_fixed_angle_deg": 0.0,
    "lfe_cutoff": 120,
    "enable_drums": True,
    "enable_bass": True,
    "enable_other": True,
    "random_seed": 42  # 用于生成初始相位
}

# 参数说明和范围
PARAM_INFO = {
    "rotation_speed_drums": "鼓的旋转速度 (Hz)，正=顺时针，负=逆时针，范围 -0.3~0.3",
    "rotation_speed_bass": "贝斯的旋转速度 (Hz)，范围 -0.3~0.3",
    "rotation_speed_other": "其他乐器的旋转速度 (Hz)，范围 -0.3~0.3",
    "rotate_vocals": "人声是否旋转（若不旋转，则固定在下方角度）",
    "vocal_fixed_angle_deg": "人声固定角度（度），0°为正前方，正值为顺时针方向",
    "lfe_cutoff": "低音炮截止频率 (Hz)，通常 80~120",
    "enable_drums": "启用鼓的环绕",
    "enable_bass": "启用贝斯的环绕",
    "enable_other": "启用其他乐器的环绕",
    "random_seed": "随机种子（确保每次生成一致）"
}

class ConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("7.1环绕声参数配置")
        self.root.geometry("500x600")
        self.load_config()

        # 创建界面
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 乐器组
        inst_frame = ttk.LabelFrame(main_frame, text="乐器环绕参数", padding="5")
        inst_frame.pack(fill=tk.X, pady=5)

        self.create_slider(inst_frame, "鼓速度 (Hz):", "rotation_speed_drums", -0.3, 0.3, 0.01)
        self.create_checkbox(inst_frame, "启用鼓", "enable_drums")

        self.create_slider(inst_frame, "贝斯速度 (Hz):", "rotation_speed_bass", -0.3, 0.3, 0.01)
        self.create_checkbox(inst_frame, "启用贝斯", "enable_bass")

        self.create_slider(inst_frame, "其他速度 (Hz):", "rotation_speed_other", -0.3, 0.3, 0.01)
        self.create_checkbox(inst_frame, "启用其他", "enable_other")

        # 人声组
        vocal_frame = ttk.LabelFrame(main_frame, text="人声参数", padding="5")
        vocal_frame.pack(fill=tk.X, pady=5)

        self.create_checkbox(vocal_frame, "人声旋转", "rotate_vocals")
        self.create_slider(vocal_frame, "人声固定角度 (°):", "vocal_fixed_angle_deg", -180, 180, 1)

        # 其他参数
        other_frame = ttk.LabelFrame(main_frame, text="其他参数", padding="5")
        other_frame.pack(fill=tk.X, pady=5)

        self.create_slider(other_frame, "LFE截止频率 (Hz):", "lfe_cutoff", 20, 250, 1)
        self.create_slider(other_frame, "随机种子:", "random_seed", 0, 1000, 1, is_int=True)

        # 预设下拉框
        preset_frame = ttk.Frame(main_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        ttk.Label(preset_frame, text="加载预设:").pack(side=tk.LEFT, padx=5)
        self.preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_var, 
                                    values=["默认", "鼓主导", "贝斯主导", "其他主导", "随机混合"], 
                                    state="readonly", width=15)
        preset_combo.pack(side=tk.LEFT)
        preset_combo.bind("<<ComboboxSelected>>", self.load_preset)
        ttk.Button(preset_frame, text="应用", command=self.apply_preset).pack(side=tk.LEFT, padx=5)

        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="恢复默认", command=self.reset_to_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="退出", command=root.quit).pack(side=tk.RIGHT, padx=5)

        # 状态栏
        self.status = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, pady=5)

    def create_slider(self, parent, label, key, from_, to, resolution, is_int=False):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text=label, width=20, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.DoubleVar(value=self.config.get(key, DEFAULT_CONFIG[key]))
        setattr(self, key + "_var", var)
        scale = ttk.Scale(frame, from_=from_, to=to, orient=tk.HORIZONTAL, variable=var, 
                          command=lambda v, k=key: self.update_label(k, v))
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        value_label = ttk.Label(frame, text=f"{var.get():.2f}" + ("" if not is_int else ""), width=8)
        value_label.pack(side=tk.LEFT)
        # 存储标签引用以便更新
        setattr(self, key + "_label", value_label)
        # 提示
        ttk.Label(frame, text="?").pack(side=tk.LEFT)
        self.create_tooltip(frame, PARAM_INFO[key])

    def create_checkbox(self, parent, label, key):
        var = tk.BooleanVar(value=self.config.get(key, DEFAULT_CONFIG[key]))
        setattr(self, key + "_var", var)
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.pack(anchor=tk.W, pady=2)
        self.create_tooltip(cb, PARAM_INFO[key])

    def update_label(self, key, value):
        label = getattr(self, key + "_label")
        var = getattr(self, key + "_var")
        label.config(text=f"{var.get():.2f}")

    def create_tooltip(self, widget, text):
        def show_tip(event):
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tip, text=text, background="#ffffe0", relief=tk.SOLID, borderwidth=1)
            label.pack()
            widget.tip = tip
            widget.bind("<Leave>", hide_tip)
        def hide_tip(event):
            if hasattr(widget, "tip"):
                widget.tip.destroy()
        widget.bind("<Enter>", show_tip)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except:
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()

    def save_config(self):
        # 从变量收集数据
        for key in DEFAULT_CONFIG:
            if hasattr(self, key + "_var"):
                var = getattr(self, key + "_var")
                if isinstance(var, tk.DoubleVar) or isinstance(var, tk.BooleanVar):
                    self.config[key] = var.get()
        # 保存到文件
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.status.config(text="配置已保存")
            messagebox.showinfo("成功", f"配置已保存到 {CONFIG_FILE}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def reset_to_default(self):
        self.config = DEFAULT_CONFIG.copy()
        self.update_ui_from_config()
        self.status.config(text="已恢复默认配置")

    def update_ui_from_config(self):
        for key, value in self.config.items():
            if hasattr(self, key + "_var"):
                var = getattr(self, key + "_var")
                if isinstance(var, tk.DoubleVar):
                    var.set(value)
                    self.update_label(key, None)
                elif isinstance(var, tk.BooleanVar):
                    var.set(value)

    def load_preset(self, event=None):
        preset = self.preset_var.get()
        if preset == "默认":
            self.config = DEFAULT_CONFIG.copy()
        elif preset == "鼓主导":
            self.config = DEFAULT_CONFIG.copy()
            self.config.update({
                "rotation_speed_drums": 0.05,
                "rotation_speed_bass": 0.05,
                "rotation_speed_other": 0.05,
                "random_seed": 123
            })
        elif preset == "贝斯主导":
            self.config.update({
                "rotation_speed_drums": 0.08,
                "rotation_speed_bass": 0.12,
                "rotation_speed_other": 0.08,
                "random_seed": 456
            })
        elif preset == "其他主导":
            self.config.update({
                "rotation_speed_drums": 0.15,
                "rotation_speed_bass": -0.1,
                "rotation_speed_other": 0.2,
                "random_seed": 789
            })
        elif preset == "随机混合":
            self.config.update({
                "rotation_speed_drums": 0.2,
                "rotation_speed_bass": -0.15,
                "rotation_speed_other": 0.1,
                "random_seed": 999
            })
        self.update_ui_from_config()

    def apply_preset(self):
        self.load_preset()
        self.status.config(text=f"已加载预设: {self.preset_var.get()}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigGUI(root)
    root.mainloop()