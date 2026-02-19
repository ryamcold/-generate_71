# generate_71 环绕声生成器

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/ryamcold/-generate_71)](https://github.com/ryamcold/-generate_71/releases)
[![Downloads](https://img.shields.io/github/downloads/ryamcold/-generate_71/total)](https://github.com/ryamcold/-generate_71/releases)

**将普通立体声音乐智能转换为 7.1 声道环绕声，体验沉浸式音频效果。**

---

## 📖 项目简介

本项目基于 Facebook Research 的 [Demucs](https://github.com/facebookresearch/demucs) 音源分离模型和 Ambisonics 空间音频技术，能够自动将任意立体声音乐（MP3、FLAC、WAV 等）转换为 **7.1 声道环绕声文件**。它不仅能精准分离人声与乐器，还能让乐器在空间中环绕旋转，营造出身临其境的听觉体验。

无论是欣赏音乐、制作视频配乐，还是测试环绕声系统，本工具都能为您带来专业级的环绕声体验。

---

## ✨ 核心特性

- **智能音源分离**：使用 Demucs 4 模型分离人声、鼓、贝斯及其他乐器，分离精度高。
- **动态环绕声场**：采用一阶 Ambisonics 技术，实现平滑自然的声像移动，避免简单的声道跳变。
- **参数灵活可调**：提供图形配置界面，可独立调整各乐器旋转速度、人声是否旋转、低音炮频率等。
- **全自动环境配置**：主脚本自动创建虚拟环境、安装依赖（使用清华源加速）、创建输入输出文件夹，开箱即用。
- **GPU 加速**：自动检测 CUDA，支持 NVIDIA GPU 加速处理（处理速度快 3~5 倍）。
- **批量处理**：一键处理 `Input` 文件夹中的所有音频文件，输出到 `Output` 文件夹。
- **跨平台支持**：Windows、Linux、macOS 均可运行。

---

## 📋 系统要求

- **操作系统**：Windows 10/11、Linux、macOS
- **Python**：3.8 或更高版本
- **磁盘空间**：至少 5 GB（用于存放虚拟环境、依赖和模型）
- **内存**：推荐 8 GB 以上
- **GPU（可选）**：NVIDIA 显卡，支持 CUDA（用于加速）

---

## 🚀 快速开始

### 方法一：一键运行（推荐）

1. **下载本项目**：
   ```bash
   git clone https://github.com/ryamcold/-generate_71.git
   cd -generate_71
   ```

2. **直接运行主脚本**：
   ```bash
   python generate_71_batch_v2.py
   ```
   - 首次运行会自动创建虚拟环境 `surround_env`。
   - 自动安装所有依赖（使用清华源加速）。
   - 自动下载 Demucs 模型（约 1.5 GB，请保持网络畅通）。
   - 自动创建 `Input` 和 `Output` 文件夹。

3. **将您的音频文件放入 `Input` 文件夹**（支持 `.mp3`、`.wav`、`.flac`、`.m4a`、`.ogg`、`.aac`）。

4. **等待处理完成**，生成的 7.1 声道文件将保存在 `Output` 文件夹中。

### 方法二：手动安装（高级用户）

如果您希望手动控制环境，可以按以下步骤操作：

1. **创建并激活虚拟环境**：
   ```bash
   python -m venv surround_env
   # Windows
   surround_env\Scripts\activate
   # Linux/macOS
   source surround_env/bin/activate
   ```

2. **安装依赖**（使用清华源加速）：
   ```bash
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy scipy soundfile torch demucs
   ```

3. **运行主程序**：
   ```bash
   python generate_71_batch_v2.py
   ```

---

## 🎛️ 使用方法

### 1. 调整环绕参数（可选）

运行图形配置界面，可实时调整各项参数：
```bash
python config_gui.py
```
调整后点击 **保存配置**，主程序将自动读取新参数。

### 2. 批量处理音频

将音频文件放入 `Input` 文件夹，然后运行：
```bash
python generate_71_batch_v2.py
```
脚本会自动处理所有支持的音频文件，并在 `Output` 文件夹生成对应的 `*_71.wav` 文件。

### 3. 高级选项

主脚本支持以下命令行参数：

| 参数 | 说明 |
|------|------|
| `--input_dir PATH` | 指定输入文件夹（默认 `Input`） |
| `--output_dir PATH` | 指定输出文件夹（默认 `Output`） |
| `--force_cpu` | 强制使用 CPU 处理（即使有 GPU） |

示例：
```bash
python generate_71_batch_v2.py --input_dir "D:\MyMusic" --output_dir "D:\SurroundMusic" --force_cpu
```

---

## ⚙️ 参数说明

通过 `config.json` 或图形界面可调整以下参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `rotation_speed_drums` | float | 0.1 | 鼓的旋转速度 (Hz)，正=顺时针，负=逆时针 |
| `rotation_speed_bass` | float | 0.1 | 贝斯的旋转速度 |
| `rotation_speed_other` | float | 0.1 | 其他乐器的旋转速度 |
| `rotate_vocals` | bool | false | 人声是否参与旋转（否则固定在左右声道） |
| `vocal_fixed_angle_deg` | float | 0.0 | 当人声旋转时，该值作为初始相位（度） |
| `lfe_cutoff` | int | 120 | 低音炮低通截止频率 (Hz)，范围 20~250 |
| `enable_drums` | bool | true | 是否启用鼓的环绕 |
| `enable_bass` | bool | true | 是否启用贝斯的环绕 |
| `enable_other` | bool | true | 是否启用其他乐器的环绕 |
| `random_seed` | int | 42 | 随机种子，用于生成初始相位（确保可重复性） |

---

## 🔧 高级用法

### 使用自定义配置文件

创建 `config.json` 文件（可参考 `config.json.example`），修改参数后运行主程序，脚本会自动读取。

### 强制使用 CPU（即使有 GPU）

```bash
python generate_71_batch_v2.py --force_cpu
```

### 单独处理特定文件

如果需要处理单个文件，可以直接使用 `process_file` 函数（需编写简单调用脚本），或暂时将其他文件移出 `Input` 文件夹。

---

## ❓ 常见问题

### Q1：为什么处理速度很慢？
- 首次运行需要下载模型和安装依赖，请耐心等待。
- 如果没有 GPU，CPU 处理一首 3 分钟歌曲约需 2~5 分钟。
- 如果有 GPU 但未启用，请检查 CUDA 是否正确安装（运行 `nvidia-smi` 查看驱动信息）。

### Q2：提示 `ffmpeg not found` 怎么办？
处理非 WAV 格式（如 MP3、FLAC）需要 ffmpeg。请根据操作系统安装：
- **Windows**：下载 ffmpeg 并添加到系统 PATH。
- **Linux**：`sudo apt install ffmpeg`
- **macOS**：`brew install ffmpeg`
安装后重新运行脚本。

### Q3：生成的 7.1 文件播放时没有环绕感？
- 请确保播放器（如 VLC、PotPlayer）的音频输出设置为 **7.1 扬声器**。
- 检查系统声音设置中是否已配置为 7.1 模式。
- 使用杜比官方测试文件验证您的环绕声系统是否正常工作。

### Q4：如何卸载虚拟环境？
直接删除 `surround_env` 文件夹即可。

---

## 🤝 贡献指南

欢迎提交 Issue 或 Pull Request 改进本项目。如果您有好的建议或发现了 bug，请通过 GitHub Issues 告知。

### 开发环境设置
1. Fork 本仓库。
2. 克隆到本地。
3. 创建虚拟环境并安装开发依赖。
4. 修改代码并测试。
5. 提交 Pull Request。

---

## 📄 许可证

本项目采用 **MIT 许可证**。您可以自由使用、修改和分发，但需保留原版权声明。

---

## 🙏 致谢

- [Demucs](https://github.com/facebookresearch/demucs) - Facebook Research 的音源分离模型
- [PyTorch](https://pytorch.org/) - 深度学习框架
- [Ambisonics](https://en.wikipedia.org/wiki/Ambisonics) - 空间音频技术

---

**立即体验 7.1 环绕声的魅力！** 🎧
