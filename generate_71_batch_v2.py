#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
7.1声道环绕声生成器 - 超级集成版（修正版）
功能：
- 自动创建虚拟环境（如果不在环境中）
- 自动安装依赖（清华源）
- 自动创建 Input/Output 文件夹
- 自动加载模型并处理音频
- 支持GPU加速（自动检测并安装CUDA版PyTorch）
"""

import os
import sys
import subprocess
import importlib.util
import platform
import json
import argparse
from pathlib import Path

# ==================== 配置区域 ====================
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "surround_env")
INPUT_DIR = os.path.join(PROJECT_DIR, "Input")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "Output")
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
REQUIRED_PACKAGES = [
    'numpy',
    'scipy',
    'soundfile',
    'torch',
    'demucs'
]
TSINGHUA_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
CUDA_TORCH_URL = "https://download.pytorch.org/whl/cu118"
CPU_TORCH_URL = "https://download.pytorch.org/whl/cpu"

# ==================== 环境准备函数 ====================
def is_in_virtualenv():
    """判断是否在虚拟环境中"""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def create_virtualenv():
    """创建虚拟环境（如果不存在）"""
    if os.path.exists(VENV_DIR):
        print(f"✅ 虚拟环境已存在: {VENV_DIR}")
        return True
    print("🔧 正在创建虚拟环境...")
    try:
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
        print("✅ 虚拟环境创建成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 创建虚拟环境失败: {e}")
        return False

def get_venv_python():
    """获取虚拟环境中的Python解释器路径"""
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")

def restart_in_venv():
    """在虚拟环境中重新运行当前脚本"""
    venv_python = get_venv_python()
    if not os.path.exists(venv_python):
        print("❌ 虚拟环境Python解释器不存在")
        return False
    print("🔄 正在切换到虚拟环境重新运行...")
    subprocess.run([venv_python] + sys.argv)
    sys.exit(0)

def check_packages():
    """检查所需包是否已安装，返回缺失列表"""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    return missing

def install_packages(missing_packages, use_cuda=True):
    """安装缺失的包（使用清华源）"""
    if not missing_packages:
        return True
    print(f"📦 正在安装缺失的依赖: {', '.join(missing_packages)}")
    
    # 构建pip命令
    pip_cmd = [sys.executable, "-m", "pip", "install", "-i", TSINGHUA_URL]
    
    # 特殊处理torch和torchaudio，使用指定源
    torch_needed = any(p in ['torch', 'torchaudio'] for p in missing_packages)
    if torch_needed:
        # 先卸载现有的torch（如果有）
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "torch", "torchaudio"], 
                       capture_output=True)
        # 根据是否使用CUDA选择源
        torch_url = CUDA_TORCH_URL if use_cuda else CPU_TORCH_URL
        pip_cmd += ["--index-url", torch_url]
        # 移除缺失列表中的torch/torchaudio，后面单独装
        missing_packages = [p for p in missing_packages if p not in ['torch', 'torchaudio']]
        # 添加torch和torchaudio
        missing_packages += ["torch", "torchaudio"]
    
    # 安装
    try:
        subprocess.run(pip_cmd + missing_packages, check=True)
        print("✅ 依赖安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def check_cuda_available():
    """检查是否有NVIDIA GPU（通过nvidia-smi）"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def create_folders():
    """创建Input和Output文件夹"""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✅ 输入文件夹: {INPUT_DIR}")
    print(f"✅ 输出文件夹: {OUTPUT_DIR}")

def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ ffmpeg 已安装")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ ffmpeg 未找到，处理非WAV格式时需要，建议安装")
        return False

# ==================== 核心处理函数 ====================
def lowpass_filter(data, cutoff, fs, order=4):
    """低通滤波器（内部导入所需模块）"""
    from scipy.signal import butter, filtfilt
    import numpy as np
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data, axis=-1)

def read_audio_safe(input_path, target_sr, target_channels, device):
    """安全读取音频文件，先尝试demucs，失败则用soundfile"""
    import soundfile as sf
    import torch
    import numpy as np
    from demucs.audio import AudioFile, convert_audio
    
    # 尝试使用 demucs 的 AudioFile
    try:
        af = AudioFile(input_path)
        # 新版 demucs 可能返回 (wav, sr) 或直接 wav，需处理
        result = af.read()
        if isinstance(result, tuple) and len(result) == 2:
            wav, sr = result
        else:
            # 假设只返回 wav，采样率需从对象获取
            wav = result
            sr = af.samplerate
        wav = wav.to(device)
        wav = convert_audio(wav, sr, target_sr, target_channels)
        return wav.unsqueeze(0)
    except Exception as e1:
        print(f"demucs AudioFile 读取失败: {e1}，尝试使用 soundfile...")
        try:
            data, sr = sf.read(input_path)
            if data.ndim == 1:
                data = np.stack([data, data], axis=1)
            elif data.shape[1] > 2:
                data = data[:, :2]
            data = data.T  # 转置为 (channels, samples)
            wav = torch.from_numpy(data).float().to(device)
            wav = convert_audio(wav, sr, target_sr, target_channels)
            return wav.unsqueeze(0)
        except Exception as e2:
            raise RuntimeError(f"所有读取方式均失败: {e2}")

def ambisonics_encode_decode(sources_signals, source_azimuths, speaker_azimuths):
    """一阶Ambisonics编码解码（内部导入numpy）"""
    import numpy as np
    num_sources = len(sources_signals)
    num_samples = sources_signals[0].shape[0]
    num_speakers = len(speaker_azimuths)
    W = np.zeros(num_samples, dtype=np.float32)
    X = np.zeros(num_samples, dtype=np.float32)
    Y = np.zeros(num_samples, dtype=np.float32)
    for src_idx, sig in enumerate(sources_signals):
        az = source_azimuths[src_idx]
        w_coeff = 1.0 / np.sqrt(2)
        x_coeff = np.cos(az)
        y_coeff = np.sin(az)
        W += sig * w_coeff
        X += sig * x_coeff
        Y += sig * y_coeff
    decoded = np.zeros((num_samples, num_speakers), dtype=np.float32)
    for spk_idx, spk_az in enumerate(speaker_azimuths):
        decoded[:, spk_idx] = W + X * np.cos(spk_az) + Y * np.sin(spk_az)
    return decoded

def process_file(input_path, output_path, model, device, config):
    """处理单个音频文件"""
    import numpy as np
    import torch
    import soundfile as sf
    from demucs.apply import apply_model
    
    print(f"🎵 正在处理：{os.path.basename(input_path)}")
    try:
        wav = read_audio_safe(input_path, model.samplerate, model.audio_channels, device)

        with torch.no_grad():
            sources = apply_model(model, wav, device=device, shifts=1, split=True, overlap=0.25, progress=True)
        sources = sources.cpu().numpy()[0]  # (4, channels, samples)

        # 提取各音源 (顺序: 0-鼓, 1-贝斯, 2-其他, 3-人声)
        drums   = sources[0].T  # (samples, channels)
        bass    = sources[1].T
        other   = sources[2].T
        vocals  = sources[3].T

        samplerate = model.samplerate
        num_samples = vocals.shape[0]
        t = np.arange(num_samples) / samplerate

        # 转换为单声道
        drums_mono   = (drums[:, 0] + drums[:, 1]) * 0.5
        bass_mono    = (bass[:, 0] + bass[:, 1]) * 0.5
        other_mono   = (other[:, 0] + other[:, 1]) * 0.5
        vocals_mono  = (vocals[:, 0] + vocals[:, 1]) * 0.5

        # 初始化7.1声道数组 (FL, FR, FC, LFE, SL, SR, BL, BR)
        surround = np.zeros((num_samples, 8), dtype=np.float32)

        # 人声处理
        if config.get("rotate_vocals", False):
            vocal_speed = config.get("rotation_speed_drums", 0.1)
            vocal_init = 0.0
            vocal_az = vocal_init - 2 * np.pi * vocal_speed * t
            sources_signals = []
            source_azimuths = []
            if config.get("enable_drums", True):
                sources_signals.append(drums_mono)
                source_azimuths.append(config["rotation_speed_drums"] * -2*np.pi*t + 0)
            if config.get("enable_bass", True):
                sources_signals.append(bass_mono)
                source_azimuths.append(config["rotation_speed_bass"] * -2*np.pi*t + 2*np.pi/3)
            if config.get("enable_other", True):
                sources_signals.append(other_mono)
                source_azimuths.append(config["rotation_speed_other"] * -2*np.pi*t + 4*np.pi/3)
            sources_signals.append(vocals_mono)
            source_azimuths.append(vocal_az)
        else:
            # 人声不旋转，保留原始立体声
            surround[:, 0] += vocals[:, 0]
            surround[:, 1] += vocals[:, 1]
            sources_signals = []
            source_azimuths = []
            if config.get("enable_drums", True):
                sources_signals.append(drums_mono)
                source_azimuths.append(config["rotation_speed_drums"] * -2*np.pi*t + 0)
            if config.get("enable_bass", True):
                sources_signals.append(bass_mono)
                source_azimuths.append(config["rotation_speed_bass"] * -2*np.pi*t + 2*np.pi/3)
            if config.get("enable_other", True):
                sources_signals.append(other_mono)
                source_azimuths.append(config["rotation_speed_other"] * -2*np.pi*t + 4*np.pi/3)

        # 扬声器方位角（ITU-R BS.775 7.1布局）
        speaker_azimuths = np.array([
            np.pi/6,       # FL  30°
            -np.pi/6,      # FR -30°
            110 * np.pi/180,   # SL 110°
            -110 * np.pi/180,  # SR -110°
            150 * np.pi/180,   # BL 150°
            -150 * np.pi/180   # BR -150°
        ])

        if sources_signals:
            decoded = ambisonics_encode_decode(sources_signals, source_azimuths, speaker_azimuths)
            surround[:, 0] += decoded[:, 0]  # FL
            surround[:, 1] += decoded[:, 1]  # FR
            surround[:, 4] += decoded[:, 2]  # SL
            surround[:, 5] += decoded[:, 3]  # SR
            surround[:, 6] += decoded[:, 4]  # BL
            surround[:, 7] += decoded[:, 5]  # BR

        # LFE通道（低音炮）
        drums_low = lowpass_filter(drums_mono, config["lfe_cutoff"], samplerate)
        bass_low  = lowpass_filter(bass_mono, config["lfe_cutoff"], samplerate)
        surround[:, 3] += drums_low * 0.6 + bass_low * 0.9

        # 归一化防削波
        max_peak = np.max(np.abs(surround))
        if max_peak > 0:
            surround *= 0.95 / max_peak

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        sf.write(output_path, surround, samplerate, subtype='PCM_24')
        print(f"✅ 已生成：{os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"❌ 处理失败：{e}")
        return False

def load_config():
    """加载配置文件"""
    default_config = {
        "rotation_speed_drums": 0.1,
        "rotation_speed_bass": 0.1,
        "rotation_speed_other": 0.1,
        "rotate_vocals": False,
        "vocal_fixed_angle_deg": 0.0,
        "lfe_cutoff": 120,
        "enable_drums": True,
        "enable_bass": True,
        "enable_other": True,
        "random_seed": 42
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            for k, v in default_config.items():
                config.setdefault(k, v)
            return config
        except:
            return default_config
    else:
        return default_config

# ==================== 主程序 ====================
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="7.1声道环绕声生成器（超级集成版）")
    parser.add_argument("--input_dir", default=INPUT_DIR, help="输入音频文件夹路径")
    parser.add_argument("--output_dir", default=OUTPUT_DIR, help="输出文件夹路径")
    parser.add_argument("--force_cpu", action="store_true", help="强制使用CPU（即使有GPU）")
    args = parser.parse_args()

    # 步骤1：确保在虚拟环境中
    if not is_in_virtualenv():
        print("🌱 未检测到虚拟环境，准备创建/进入...")
        if create_virtualenv():
            restart_in_venv()
        else:
            print("❌ 无法创建虚拟环境，退出")
            sys.exit(1)

    # 此时已在虚拟环境中
    print(f"✅ 当前在虚拟环境中: {sys.prefix}")

    # 步骤2：创建文件夹
    create_folders()

    # 步骤3：检查ffmpeg
    check_ffmpeg()

    # 步骤4：检查依赖并安装
    missing = check_packages()
    if missing:
        # 检测是否支持CUDA
        use_cuda = (not args.force_cpu) and check_cuda_available()
        if use_cuda:
            print("🎮 检测到NVIDIA GPU，将安装CUDA版PyTorch")
        else:
            print("💻 未检测到GPU或强制使用CPU，将安装CPU版PyTorch")
        if not install_packages(missing, use_cuda=use_cuda):
            print("❌ 依赖安装失败，无法继续")
            sys.exit(1)
        # 安装后可能需要重新导入，提示重启脚本
        print("🔄 依赖安装完成，建议重新运行脚本以确保所有模块可用")
        # 此处不自动重启，继续尝试运行（可能部分模块还未加载）

    # 步骤5：加载模型
    print("⏳ 正在加载 Demucs 模型...")
    from demucs import pretrained
    import torch
    device = 'cuda' if (torch.cuda.is_available() and not args.force_cpu) else 'cpu'
    print(f"🖥️ 使用设备: {device}")
    model = pretrained.get_model('htdemucs')
    model.to(device)
    model.eval()

    # 步骤6：获取音频文件列表
    audio_exts = ('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac')
    input_dir = args.input_dir
    if not os.path.exists(input_dir):
        print(f"❌ 输入目录不存在：{input_dir}")
        return

    files = [f for f in os.listdir(input_dir) 
             if f.lower().endswith(audio_exts) and not f.endswith('_71.wav')]

    if not files:
        print(f"📂 在 {input_dir} 中没有找到可处理的音频文件。")
        return

    print(f"🔍 找到 {len(files)} 个待处理文件，将逐一转换...")

    # 步骤7：加载配置
    config = load_config()
    print("📋 当前配置:")
    for k, v in config.items():
        print(f"   {k}: {v}")

    # 步骤8：处理每个文件
    success_count = 0
    for file in files:
        input_path = os.path.join(input_dir, file)
        base, ext = os.path.splitext(file)
        output_filename = f"{base}_71.wav"
        output_path = os.path.join(args.output_dir, output_filename)

        if process_file(input_path, output_path, model, device, config):
            success_count += 1

    print(f"\n🎉 全部完成！成功处理 {success_count}/{len(files)} 个文件。")

if __name__ == "__main__":
    main()
