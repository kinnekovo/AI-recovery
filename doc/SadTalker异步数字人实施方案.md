# SadTalker 异步数字人实施方案

## 目标与边界

本阶段把患者上传的授权正面照与系统生成的腾讯云 TTS 音频合成为可播放的 MP4，使训练页展示真实口型、眨眼和轻微头部动作。SadTalker 只负责照片加音频到视频；文本到音频仍由现有 TTS Provider 完成。

本阶段不承诺五秒内生成完整视频，也不训练个人模型。页面必须保持可用：视频生成失败、超时、未配置或未上传照片时，自动回退到现有的“静态头像＋真实 TTS 音频”链路。

## 目标链路

```text
训练页请求示范文本
  -> 腾讯云 TTS 生成或命中 WAV 缓存
  -> 创建/复用 avatar_video_task
  -> 独立 GPU Worker 异步生成 MP4
  -> 前端轮询任务状态
  -> 成功：只播放带声音的 MP4
  -> 失败/超时：播放 WAV，保留静态头像
```

同一人物照片、同一音频和同一推理配置只生成一次；任务成功后的 MP4 通过现有受权限保护的 `/api/files/{id}/content` 下载，不公开本地存储路径。

## 实施架构

### 后端主服务

- 保持现有 FastAPI、PostgreSQL、文件权限和 TTS Provider。
- `POST /api/training/avatar-speech` 在返回音频时一并返回视频任务摘要。
- `GET /api/avatar-video-tasks/{id}` 仅允许任务所属患者查询。
- 主服务不导入 SadTalker、Torch 或 GPU 依赖。

### 视频任务和文件

- `avatar_video_tasks` 保存状态：`queued`、`running`、`succeeded`、`failed`。
- `files.file_type` 增加 `generated_avatar_video`，文件放在 `storage/generated-avatar-videos/`。
- 缓存键由人物头像版本、音频文件、模型版本和推理配置共同计算。
- 任务失败保存安全错误信息和耗时；不得把命令行、密钥或本地路径返回前端。

### 独立 Worker

Worker 以独立 Python 环境运行，一次只取一个任务：

1. 原子领取 `queued` 任务并标记 `running`。
2. 校验头像、音频、用户授权和文件状态。
3. 调用 Provider，写入临时目录。
4. 规范化为浏览器可播放的 H.264/AAC MP4。
5. 创建 `FileAsset`，关联任务并标记成功；异常则标记失败。

第一版提供 `mock` Provider 作为自动测试和演示备用；真实 `sadtalker` Provider 只通过明确环境变量启用。Worker 的并发固定为 1，避免单张 GPU 的显存竞争。

## SadTalker 本机运行门槛

SadTalker 必须安装在独立目录和独立 Conda 环境。官方旧版说明以 Python 3.8/PyTorch CUDA 11.3 为例；本机 RTX 5060 属于新显卡，不能在未验收前直接把旧依赖装进项目后端环境。

验收顺序：

1. 独立环境中确认 `torch.cuda.is_available()` 为真且识别 RTX 5060。
2. 使用一张胸部以上正面照和 3 秒 WAV 跑通官方 CLI。
3. 检查 MP4 是否有清晰口型、眨眼、轻微头动，且没有灰色遮罩。
4. 分别记录 3、8、15 秒音频的冷启动、热启动、显存峰值和输出大小。
5. 配置 `AVATAR_VIDEO_PROVIDER=sadtalker` 后才接入真实 Worker。

建议初始推理配置为 `crop` 人脸预处理、512 画面、关闭增强器。为保留头部运动，不使用 `--still`。输出采用 25fps、H.264、yuv420p、AAC 和 faststart。

## 配置项

```env
AVATAR_VIDEO_PROVIDER=mock
SADTALKER_HOME=../runtimes/SadTalker
SADTALKER_PYTHON=
SADTALKER_TIMEOUT_SECONDS=180
SADTALKER_PREPROCESS=crop
SADTALKER_FACE_SIZE=512
SADTALKER_USE_ENHANCER=false
FFMPEG_BIN=ffmpeg
AVATAR_VIDEO_FRONTEND_FALLBACK_SECONDS=60
AVATAR_VIDEO_WORKER_POLL_SECONDS=1
```

`mock` 是默认值，确保没有安装模型时，开发、自动测试和既有训练流程都可继续演示。真实模型必须通过 `SADTALKER_HOME`、`SADTALKER_PYTHON` 和 `AVATAR_VIDEO_PROVIDER=sadtalker` 显式开启。

SadTalker 运行环境首次安装或更新依赖后，执行下列命令修复其旧版 BasicSR 与新版 torchvision 的兼容导入，再运行 `inference.py --help` 进行探测：

```powershell
cd backend
python scripts/prepare_sadtalker_runtime.py --python ../runtimes/SadTalker/.venv/Scripts/python.exe
```

`FFMPEG_BIN` 必须指向可执行的 ffmpeg；Worker 会将模型原始输出统一转为 H.264/yuv420p/AAC/faststart，失败则不保存该视频并回退到 WAV，避免向浏览器发出不可播放的文件。规范化会依次尝试 `libx264`、`h264_nvenc`、`h264_mf`：这样剪映自带 ffmpeg 不含 `libx264` 时，仍可在 NVIDIA 设备上使用 `h264_nvenc` 产出浏览器可播放的视频。

权重就绪后，用下面的命令完成可复现的 Day-1 验收；脚本会拒绝 CPU 环境、缺失权重和不可解码的视频，避免误把 Mock 或静态图当作真实数字人：

```powershell
cd backend
python scripts/validate_sadtalker_runtime.py `
  --python ../runtimes/SadTalker/.venv/Scripts/python.exe `
  --home ../runtimes/SadTalker `
  --ffmpeg "D:\\Installment\\JianyingPro\\11.3.0.14362\\ffmpeg.exe" `
  --image "D:\\path\\to\\portrait.jpg" --audio "D:\\path\\to\\speech.wav"
```

### 当前环境验收记录（2026-09-12）

- 已完成：官方 SadTalker 运行目录、Python 3.10 独立虚拟环境、BasicSR/torchvision 兼容补丁；`inference.py --help` 可正常启动。
- 已确认：`torch 2.11.0+cu128`、`torchvision 0.26.0+cu128`、`torchaudio 2.11.0+cu128` 均在 SadTalker 独立环境中可用；`torch.cuda.is_available()` 为 `True`，设备为 NVIDIA GeForce RTX 5060 Laptop GPU。
- 已确认：`mapping_00109-model.pth.tar`、`mapping_00229-model.pth.tar` 与 `SadTalker_V0.0.2_512.safetensors` 已到位且完成 SHA-256 校验；关闭增强器时使用本地 GFPGAN 检测权重，避免运行时联网下载。
- 已通过：以 SadTalker 自带的官方示例人物与中文音频进行真实 GPU 验收，生成并解码了非空 MP4（268,901 bytes）。该验证未使用任何用户上传或第三方肖像。
- 已启用：本机 `backend/.env` 配置为 `AVATAR_VIDEO_PROVIDER=sadtalker`，超时为 900 秒。Provider 会在子进程环境中临时注入 `FFMPEG_BIN` 的目录，SadTalker 内部合成不依赖全局系统 PATH；失败任务在相同文案再次请求时会复用已缓存 WAV 并重新入队。
- 临时演示配置：腾讯云 TTS 资源包额度耗尽时，将 `TTS_PROVIDER=windows`。它调用本机已安装的 Windows 中文 SAPI 音色，将当前训练文案合成为 WAV 后再交给 SadTalker；不联网、不创建音色 ID，也不代表个性化音色。恢复腾讯云额度后可改回 `TTS_PROVIDER=tencent`。

### Windows 手动配置步骤（RTX 50 系显卡）

> 以下步骤在项目已存在 `runtimes/SadTalker`、`runtimes/Python310` 与 `runtimes/SadTalker/.venv` 的前提下执行。不要把 Torch 安装进 `backend` 的主环境。

1. 优先从 SadTalker 官方扩展代码使用的 Hugging Face 仓库 [`vinthony/SadTalker-V002rc`](https://huggingface.co/vinthony/SadTalker-V002rc/tree/main) 下载；它的文件页直接列出新版本所需的 512 模型与两个 MappingNet。不要下载名称含 `gfpgan` 的 Offline Patch。初始配置只使用 512 模型，下载到 `checkpoints` 后必须存在：

   ```text
   runtimes/SadTalker/checkpoints/mapping_00109-model.pth.tar
   runtimes/SadTalker/checkpoints/mapping_00229-model.pth.tar
   runtimes/SadTalker/checkpoints/SadTalker_V0.0.2_512.safetensors
   ```

   关闭 `SADTALKER_USE_ENHANCER` 时不需要下载 GFPGAN 的额外权重。

2. 在 PowerShell 的项目根目录安装与本机 RTX 50 系兼容的 CUDA 12.8 版 Torch（不能沿用官方旧 README 的 `torch 1.12 + cu113`）：

   ```powershell
   $py = '.\runtimes\SadTalker\.venv\Scripts\python.exe'
   & $py -m pip uninstall -y torch torchvision torchaudio
   & $py -m pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
   & $py -m pip install 'setuptools<81'
   ```

   若使用手工下载的 wheel，三者必须来自同一套 `cu128`、同一版本组合，且必须是 **`cp310-cp310-win_amd64.whl`**（项目 SadTalker 环境固定使用 Python 3.10）。`cp313` / Python 3.13 的文件即使名称版本相同也不能安装。下载 wheelhouse 时使用 `runtimes/SadTalker/.venv` 内较新的 pip，并同时指定 `--extra-index-url https://pypi.org/simple`，以正确获取 `typing-extensions` 等常规依赖；用 `pip install --no-index --find-links <wheel目录> ...` 安装即可。

3. 重新应用项目提供的兼容补丁并确认 GPU：

   ```powershell
   cd backend
   python scripts/prepare_sadtalker_runtime.py --python ../runtimes/SadTalker/.venv/Scripts/python.exe
   ../runtimes/SadTalker/.venv/Scripts/python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
   ```

   第二行必须是 `True`，第三行应显示 NVIDIA GPU；否则不要切换真实 Provider。

4. 用上一节的 `validate_sadtalker_runtime.py` 命令，传入一张已授权胸部以上正面照和 3 秒 WAV，完成真实 CLI 验收。

5. 仅在脚本通过后，将 `backend/.env` 改为：

   ```env
   AVATAR_VIDEO_PROVIDER=sadtalker
   SADTALKER_HOME=../runtimes/SadTalker
   SADTALKER_PYTHON=../runtimes/SadTalker/.venv/Scripts/python.exe
   SADTALKER_TIMEOUT_SECONDS=300
   SADTALKER_PREPROCESS=crop
   SADTALKER_FACE_SIZE=512
   SADTALKER_USE_ENHANCER=false
   ```

6. 分别启动 API 和 Worker：`uvicorn app.main:app --reload`、`python scripts/run_avatar_video_worker.py`。从训练页点击示范，确认先出现“动态形象正在生成”，随后播放真人口型视频；Worker 失败时应自动回退到 WAV。

常见故障：`torch.cuda.is_available()` 为 `False` 说明装到了 CPU wheel 或驱动/运行时不匹配；`functional_tensor` 错误重新运行第 3 步补丁；显存不足时将 `SADTALKER_FACE_SIZE=256`，并下载同名 `SadTalker_V0.0.2_256.safetensors`，不要同时把 512 配置保留。

## 前端体验

训练页面的数字人面板有三种视觉内容：

- 任务排队/推理中：静态头像、明确的进度文字和已等待秒数。
- 任务成功：无控制条自动播放 MP4；视频音轨是唯一声音源。
- 任务失败或超过前端等待阈值：自动使用现有 WAV 与静态头像，不中断训练。

轮询间隔一秒。用户离开页面、重复点击示范或开始下一项训练时，前端停止旧任务的轮询并忽略旧结果；后台已完成的任务仍可作为缓存复用。

## 权限、授权与清理

- 仅在头像文件存在、处于 active 状态且有图像授权时创建任务。
- 查询任务时验证 `owner_user_id`。
- 删除智能体或撤回图像授权后，不再创建视频任务，并将关联视频文件标记删除。
- 不向前端发送模型命令、系统目录或原始异常。

## 自动测试

- 缓存键稳定且会随头像/音频/配置变化。
- 无头像时不创建视频任务。
- 相同输入只返回一个活动任务或成功缓存。
- 任务仅可被所属用户读取。
- Mock Provider 生成非空 MP4 占位文件，并验证失败时前端回退音频。
- Worker 成功后保存视频文件和耗时；异常后进入 failed。
- 前端任务状态与视频播放回退在 TypeScript 构建中验证。
- 既有后端测试与前端构建必须保持通过。

## 前五天执行清单

### 第 1 天：环境门槛

建立独立运行目录和 SadTalker 环境，完成一张照片＋WAV 的人工验收；记录性能。此项依赖本机模型下载和 GPU 环境，不以 Mock 测试替代。

### 第 2 天：数据与接口

新增视频文件类型、视频任务模型、迁移、缓存键、创建任务和查询接口；实现权限检查与 Mock Provider。

### 第 3 天：Worker

实现单并发 Worker、任务领取、成功/失败持久化、文件保存、超时和日志；提供启动脚本。

### 第 4 天：前端播放

扩展示范语音响应，训练页轮询任务；成功播放 MP4，等待、超时、失败时清晰显示状态并回退音频。

### 第 5 天：联调与质量

接通真实 SadTalker 配置（若通过第 1 天门槛），完成缓存、重复点击、页面离开、超时和权限测试；运行全部后端自动测试与前端构建。

## 验收标准

1. 有授权正面照时，训练文字可获得可查询的视频任务。
2. Mock 模式下任务、权限、缓存和前端回退均可自动验证。
3. 真实模式下，生成成功的 MP4 具有声音、可在 Chrome/Edge 播放，且口型明显可见。
4. 任何视频异常都不阻塞训练，音频示范仍可完成。
5. 项目后端测试和前端构建通过。
