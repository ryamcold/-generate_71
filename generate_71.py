import os
import argparse
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, filtfilt
from demucs import pretrained
from demucs.apply import apply_model
from demucs.audio import AudioFile, convert_audio

# ---------- 低通滤波器 ----------
def lowpass_filter(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data, axis=-1)

# ---------- 安全读取音频 ----------
def read_audio_safe(input_path, target_sr, target_channels, device):
    try:
        af = AudioFile(input_path)
        wav, sr = af.read()
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
            data = data.T
            wav = torch.from_numpy(data).float().to(device)
            wav = convert_audio(wav, sr, target_sr, target_channels)
            return wav.unsqueeze(0)
        except Exception as e2:
            raise RuntimeError(f"所有读取方式均失败: {e2}")

# ---------- Ambisonics 编码解码 ----------
def ambisonics_encode_decode(sources_signals, source_azimuths, speaker_azimuths):
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

# ---------- 预设定义 ----------
PRESETS = [
    {
        'name': 'Drums Dominant',
        'speeds': [0.05, 0.05, 0.05],
        'init_phases': [0, 2*np.pi/3, 4*np.pi/3],
        'description': '鼓占主导，所有乐器慢速顺时针旋转'
    },
    {
        'name': 'Bass Dominant',
        'speeds': [0.08, 0.12, 0.08],
        'init_phases': [np.pi/2, 0, np.pi],
        'description': '贝斯占主导，贝斯旋转稍快'
    },
    {
        'name': 'Other Dominant',
        'speeds': [0.15, -0.1, 0.2],
        'init_phases': [0, np.pi, np.pi/2],
        'description': '其他乐器占主导，快速混合旋转'
    },
    {
        'name': 'Balanced Random',
        'speeds': None,
        'init_phases': None,
        'description': '能量均衡，随机生成旋转参数'
    }
]

def select_preset(energies, input_path):
    max_idx = np.argmax(energies)
    if max_idx == 0:
        preset = PRESETS[0]
        speeds = preset['speeds']
        init_phases = preset['init_phases']
    elif max_idx == 1:
        preset = PRESETS[1]
        speeds = preset['speeds']
        init_phases = preset['init_phases']
    else:
        preset = PRESETS[2]
        speeds = preset['speeds']
        init_phases = preset['init_phases']

    energies_sorted = sorted(energies, reverse=True)
    if energies_sorted[0] / (energies_sorted[1] + 1e-6) < 1.2:
        preset = PRESETS[3]
        seed = hash(input_path) % (2**32)
        rng = np.random.RandomState(seed)
        speeds = rng.uniform(-0.2, 0.2, 3)
        init_phases = rng.uniform(0, 2*np.pi, 3)
        preset_name = preset['name'] + f" (seed={seed})"
    else:
        preset_name = preset['name']

    return speeds, init_phases, preset_name

def process_file(input_path, output_path, model, device, lfe_cutoff=120, force_preset=None):
    print(f"🎵 正在处理：{os.path.basename(input_path)}")
    try:
        wav = read_audio_safe(input_path, model.samplerate, model.audio_channels, device)

        with torch.no_grad():
            sources = apply_model(model, wav, device=device, shifts=1, split=True, overlap=0.25, progress=True)
        sources = sources.cpu().numpy()[0]

        drums   = sources[0].T
        bass    = sources[1].T
        other   = sources[2].T
        vocals  = sources[3].T

        samplerate = model.samplerate
        num_samples = vocals.shape[0]
        t = np.arange(num_samples) / samplerate

        drums_mono   = (drums[:, 0] + drums[:, 1]) * 0.5
        bass_mono    = (bass[:, 0] + bass[:, 1]) * 0.5
        other_mono   = (other[:, 0] + other[:, 1]) * 0.5

        rms_drums = np.sqrt(np.mean(drums_mono**2))
        rms_bass = np.sqrt(np.mean(bass_mono**2))
        rms_other = np.sqrt(np.mean(other_mono**2))
        energies = [rms_drums, rms_bass, rms_other]

        if force_preset is not None:
            if force_preset == 0:
                speeds, init_phases, preset_name = PRESETS[0]['speeds'], PRESETS[0]['init_phases'], PRESETS[0]['name']
            elif force_preset == 1:
                speeds, init_phases, preset_name = PRESETS[1]['speeds'], PRESETS[1]['init_phases'], PRESETS[1]['name']
            elif force_preset == 2:
                speeds, init_phases, preset_name = PRESETS[2]['speeds'], PRESETS[2]['init_phases'], PRESETS[2]['name']
            else:
                seed = hash(input_path) % (2**32)
                rng = np.random.RandomState(seed)
                speeds = rng.uniform(-0.2, 0.2, 3)
                init_phases = rng.uniform(0, 2*np.pi, 3)
                preset_name = f"Forced Random (seed={seed})"
        else:
            speeds, init_phases, preset_name = select_preset(energies, input_path)

        print(f"  预设: {preset_name}")
        print(f"  能量: drums={rms_drums:.3f}, bass={rms_bass:.3f}, other={rms_other:.3f}")
        print(f"  旋转速度(Hz): drums={speeds[0]:.3f}, bass={speeds[1]:.3f}, other={speeds[2]:.3f}")

        surround = np.zeros((num_samples, 8), dtype=np.float32)

        # 人声：保留左右声道
        surround[:, 0] += vocals[:, 0]
        surround[:, 1] += vocals[:, 1]

        source_azimuths = []
        sources_signals = []
        for i, (sig, spd, init) in enumerate(zip([drums_mono, bass_mono, other_mono], speeds, init_phases)):
            az = init - 2 * np.pi * spd * t  # 顺时针旋转
            source_azimuths.append(az)
            sources_signals.append(sig)

        # 扬声器方位角（ITU-R BS.775 7.1布局）
        speaker_azimuths = np.array([
            np.pi/6,                # FL  30°
            -np.pi/6,               # FR -30°
            110 * np.pi/180,        # SL 110°
            -110 * np.pi/180,       # SR -110°
            150 * np.pi/180,        # BL 150°
            -150 * np.pi/180        # BR -150°
        ])

        decoded = ambisonics_encode_decode(sources_signals, source_azimuths, speaker_azimuths)
        surround[:, 0] += decoded[:, 0]
        surround[:, 1] += decoded[:, 1]
        surround[:, 4] += decoded[:, 2]
        surround[:, 5] += decoded[:, 3]
        surround[:, 6] += decoded[:, 4]
        surround[:, 7] += decoded[:, 5]

        # LFE通道
        drums_low = lowpass_filter(drums_mono, lfe_cutoff, samplerate)
        bass_low  = lowpass_filter(bass_mono, lfe_cutoff, samplerate)
        surround[:, 3] += drums_low * 0.6 + bass_low * 0.9

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

def main():
    parser = argparse.ArgumentParser(description="智能7.1声道音乐生成器")
    parser.add_argument("--input_dir", default=r"E:\music71bf\Input", help="输入音频文件夹路径")
    parser.add_argument("--output_dir", default=r"E:\music71bf\Output", help="输出7.1声道WAV文件夹路径")
    parser.add_argument("--lfe_cutoff", type=int, default=120, help="LFE低通截止频率(Hz)")
    parser.add_argument("--preset", type=int, choices=[0,1,2,3], default=None,
                        help="强制使用指定预设: 0=鼓主导,1=贝斯主导,2=其他主导,3=随机")
    args = parser.parse_args()

    audio_exts = ('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac')

    if not os.path.exists(args.input_dir):
        print(f"❌ 输入目录不存在：{args.input_dir}")
        return

    files = [f for f in os.listdir(args.input_dir) 
             if f.lower().endswith(audio_exts) and not f.endswith('_71.wav')]

    if not files:
        print(f"📂 在 {args.input_dir} 中没有找到可处理的音频文件。")
        return

    print(f"🔍 找到 {len(files)} 个待处理文件，将逐一转换...")

    print("⏳ 正在加载 Demucs 模型...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️ 使用设备: {device}")
    model = pretrained.get_model('htdemucs')
    model.to(device)
    model.eval()

    success_count = 0
    for file in files:
        input_path = os.path.join(args.input_dir, file)
        base, ext = os.path.splitext(file)
        output_filename = f"{base}_71.wav"
        output_path = os.path.join(args.output_dir, output_filename)

        if process_file(input_path, output_path, model, device, args.lfe_cutoff, args.preset):
            success_count += 1

    print(f"\n🎉 全部完成！成功处理 {success_count}/{len(files)} 个文件。")

if __name__ == "__main__":
    main()
