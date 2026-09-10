# راه‌اندازی و تست کامل روی سیستم GPU‌دار

این نشست (Claude Code) بدون GPU اجرا شده، پس تمام کد نوشته شده اما هرگز با
مدل‌های واقعی سنگین (`faster-whisper large-v3`, Demucs, XTTS/Piper) تست
end-to-end نشده است. این سند دقیقاً چه کاری، به چه ترتیبی، روی سیستم GPU‌دار
خودتان باید انجام شود تا کل پایپ‌لاین را تایید کنید.

## پیش‌نیازها

- یک GPU با حداقل ۸ گیگابایت VRAM (برای `faster-whisper large-v3` +
  Demucs + XTTS به‌صورت متوالی؛ همزمان اجرا نمی‌شوند چون
  `worker-gpu` با `--concurrency=1` بالا می‌آید).
- درایور NVIDIA + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  نصب‌شده (`nvidia-smi` باید هم روی هاست و هم داخل کانتینر کار کند).
- Docker + Docker Compose v2.
- `ffmpeg` روی هاست (فقط برای تست دستی خارج از کانتینر، اختیاری).

بررسی سریع قبل از شروع:

```bash
nvidia-smi                      # باید GPU را نشان دهد
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

اگر دومی کار نکرد، مشکل از NVIDIA Container Toolkit است، نه از این ریپازیتوری.

## مرحله ۱: کلون و پیکربندی

```bash
git clone <repo-url> && cd dubing_clips
git checkout claude/new-session-bvvvsu   # یا برنچی که merge شده
cp .env.example .env
```

مقادیر زیر را در `.env` حتماً پر کنید:
- `ANTHROPIC_API_KEY` — برای تشخیص هایلایت/ترجمه/کپشن.
- `POSTGRES_PASSWORD` — یک رمز واقعی.
- `WHISPER_DEVICE=cuda`, `WHISPER_COMPUTE_TYPE=float16` (پیش‌فرض‌ها درست‌اند).

## مرحله ۲: POC کیفیت TTS فارسی (ریسک فنی اصلی — قبل از هر چیز دیگر)

قبل از سرمایه‌گذاری روی یک موتور TTS خاص، کیفیت را دستی ارزیابی کنید. این
مرحله را می‌توان بدون بالا آوردن کل Docker Compose، مستقیم روی هاست اجرا کرد:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/worker-gpu.txt
pip install torch --index-url https://download.pytorch.org/whl/cu124

# یک صدای فارسی Piper دانلود کنید (نمونه: مخزن rhasspy/piper-voices روی HuggingFace)
# و مسیرش را به --piper-voice بدهید:
python scripts/tts_fa_poc.py --piper-voice ./voice_models/fa_IR-voice.onnx --try-xtts
```

خروجی‌ها در `scripts/tts_poc_output/{piper,xtts}/*.wav` ذخیره می‌شوند. با
گوش دادن دستی، بر اساس چک‌لیستی که در بالای `scripts/tts_fa_poc.py` آمده
(فهم‌پذیری، طبیعی‌بودن، تلفظ حروف خاص فارسی، سرعت) تصمیم بگیرید کدام موتور
قابل قبول است. نتیجه احتمالی (طبق پیش‌بینی اسپک):
- **XTTS با `language="fa"`** به احتمال زیاد یا اجرا نمی‌شود یا خروجی
  نامفهوم می‌دهد، چون فارسی رسماً پشتیبانی نمی‌شود.
- **Piper** با یک صدای فارسی خوب جامعه‌محور معمولاً قابل قبول‌ترین گزینه
  فعلی برای MVP است؛ کیفیتش را با گزینه‌های موجود در
  [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) مقایسه کنید.

بر اساس نتیجه، در `.env`:
```
TTS_ENGINE=piper   # یا xtts اگر واقعاً کیفیت قابل قبولی گرفتید
PIPER_FA_VOICE_PATH=/models/fa_IR-voice.onnx   # مسیر داخل کانتینر (./voice_models روی هاست)
```

اگر هیچ‌کدام کیفیت کافی نداشتند، این را به‌عنوان یک بلاکر مستند کنید — گزینه‌های
بعدی می‌توانند فاین‌تیون یک مدل TTS فارسی، یا موتورهای متن‌باز جدیدتر باشند
که موقع نوشتن این پلن هنوز منتشر نشده بودند.

## مرحله ۳: تست خطی (بدون Docker/Celery) برای دانلود + رونویسی

```bash
python scripts/run_pipeline_cli.py "https://www.youtube.com/watch?v=<ویدیوی کوتاه نمونه>" \
    --whisper-model small
```

این روی CPU با مدل کوچک اجرا می‌شود (سریع، فقط برای تایید سلامت زنجیره).
بعد از موفقیت، همان را با `--whisper-model large-v3` روی GPU امتحان کنید
(کد باید `device="cuda"` را دستی در `scripts/run_pipeline_cli.py` ست کنید یا
مستقیم از تسک Celery در مرحله بعد استفاده کنید).

## مرحله ۴: اجرای کامل با Docker Compose

```bash
docker compose up --build -d postgres redis
docker compose up --build -d api worker-cpu worker-gpu dashboard
docker compose logs -f worker-gpu   # اولین اجرا کند است: دانلود مدل large-v3
```

از داشبورد (`http://<host>:8501`) یک لینک یوتیوب کوتاه (۲-۳ دقیقه) وارد کنید،
و در تب «وضعیت Job‌ها» پیشرفت `download` → `extract_audio` → `transcribe` →
`highlight` را دنبال کنید. در صورت خطا، `docker compose logs worker-gpu` یا
`worker-cpu` را بررسی کنید — هر Job خطای خودش را در جدول `jobs` هم ذخیره می‌کند.

بعد از ظاهر شدن کلیپ‌های پیشنهادی در تب «تایید کلیپ‌ها»، حداقل یکی را تایید
کنید تا زنجیره برش → ری‌فریم → جداسازی صدا (Demucs) → ترجمه → دوبله → میکس →
زیرنویس → رندر اجرا شود. خروجی نهایی در
`storage/clips/<clip_id>/final_youtube_shorts.mp4` (و دو پریست دیگر) قرار
می‌گیرد.

## نکات دیباگ خاص GPU

- اگر `worker-gpu` با خطای CUDA OOM کرش کرد: مطمئن شوید کانتینر واقعاً با
  `--concurrency=1` بالا آمده (`docker compose exec worker-gpu ps aux`) و
  هیچ Job دیگری هم‌زمان روی همان GPU در حال اجرا نیست (مثلاً یک Jupyter
  دیگر که همان کارت را اشغال کرده).
- زمان بارگذاری اول مدل `large-v3` طولانی است (چند گیگابایت دانلود از
  HuggingFace)؛ لاگ را تا پایان صبر کنید قبل از اینکه فکر کنید Job گیر کرده.
- برای Demucs، مدل پیش‌فرض `htdemucs` هم دانلود اولیه دارد (`~/.cache/torch`
  داخل کانتینر — اگر می‌خواهید بین ری‌استارت‌ها کش بماند، یک volume برایش
  اضافه کنید).
- اگر عملاً GPU در دسترس ندارید ولی می‌خواهید فقط سیم‌کشی پایپ‌لاین را تست
  کنید: بلوک `deploy.resources.reservations.devices` را در
  `docker-compose.yml` کامنت کنید، `WHISPER_DEVICE=cpu` و
  `WHISPER_COMPUTE_TYPE=int8` بگذارید، و `WHISPER_MODEL=small` تا در زمان
  معقولی تمام شود (کیفیت رونویسی پایین‌تر از `large-v3` خواهد بود).

## چک‌لیست نهایی قبولی End-to-End

- [ ] POC صدای فارسی اجرا و یک موتور/صدا انتخاب شد (مرحله ۲)
- [ ] `run_pipeline_cli.py` با `large-v3` روی یک ویدیوی نمونه رونوشت درست تولید کرد
- [ ] یک ویدیوی کامل از داشبورد تا انتها (دانلود → کلیپ نهایی) بدون خطای بلاکینگ رد شد
- [ ] فایل `final_*.mp4` تولیدشده واقعاً صدای دوبله‌شده فارسی + موسیقی پس‌زمینه اصلی + زیرنویس دارد
- [ ] پاکسازی فایل‌های موقت (`storage/clips/<id>/dub_pieces/`, `demucs_out/`, `clip_audio.wav`, `cut.mp4` قبل از ری‌فریم) به‌درستی توسط `worker/cleanup.remove_paths` بعد از هر مرحله موفق حذف می‌شوند — با `ls -la storage/clips/<id>/` بعد از یک اجرای کامل تایید کنید که فقط فایل‌های نهایی (`reframed.mp4`, `vocals.wav`, `background.wav`, `mixed.wav`, `subtitles_fa.srt`, `final_*.mp4`, `caption_suggestion.txt`) باقی مانده‌اند
