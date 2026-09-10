# dubing_clips

ابزار داخلی/شخصی برای خودکارسازی جریان کار: گرفتن لینک یوتیوب → دانلود و رونویسی →
تشخیص خودکار بخش‌های جذاب (با تایید دستی) → برش و ری‌فریم عمودی ۹:۱۶ → ترجمه و
دوبله فارسی → زیرنویس → رندر نهایی برای اینستاگرام ریلز / تیک‌تاک / یوتیوب شورتس.

**نکته حقوقی**: دانلود و دوبله محتوای یوتیوب ممکن است با ToS یوتیوب و قوانین
کپی‌رایت در تضاد باشد. این ابزار برای استفاده شخصی/داخلی طراحی شده و مسئولیت
رعایت قوانین با کاربر نهایی است.

## معماری

- **API**: FastAPI (`api/`)
- **صف کار**: Celery + Redis، دو صف جدا: `cpu` (دانلود، تشخیص کلیپ، ترجمه، زیرنویس، رندر)
  و `gpu` (رونویسی، ری‌فریم، جداسازی صدا، دوبله) — worker-gpu باید با `--concurrency=1`
  اجرا شود تا VRAM سرریز نکند.
- **دیتابیس**: PostgreSQL + SQLAlchemy + Alembic (`models/`)
- **داشبورد تایید کلیپ**: Streamlit (`dashboard/`)
- **LLM**: Anthropic API (Claude) برای تشخیص هایلایت، ترجمه، و پیشنهاد کپشن/هشتگ

هر مرحله پایپ‌لاین یک Celery task مستقل است (`worker/`) با مدیریت خطای جدا
(`worker/job_utils.py`): اگر دوبله یک کلیپ خاص شکست بخورد، کلیپ‌های دیگر و ویدیوی
مادر متوقف نمی‌شوند.

## راه‌اندازی

```bash
cp .env.example .env   # مقادیر واقعی (ANTHROPIC_API_KEY، رمز دیتابیس) را پر کنید
docker compose up --build
```

سرویس‌ها:
- API: http://localhost:8000 (مستندات: `/docs`, سلامت: `/health`)
- داشبورد: http://localhost:8501

`worker-gpu` نیازمند NVIDIA Container Toolkit روی هاست است. اگر GPU در دسترس
نیست، بلوک `deploy.resources.reservations.devices` را در `docker-compose.yml`
کامنت کنید و `WHISPER_DEVICE=cpu` را در `.env` ست کنید (کندتر، ولی برای تست
وایرینگ پایپ‌لاین کافی است).

### راهنماهای تکمیلی

- [`docs/gpu-setup.md`](docs/gpu-setup.md): راهنمای گام‌به‌گام اجرای کامل
  end-to-end (POC صدای فارسی، رونویسی `large-v3`، پایپ‌لاین کامل) روی سیستم
  GPU‌دار خودتان — این نشست GPU نداشت، پس این بخش‌ها اینجا تست نشدند.
- [`docs/cloudflare-tunnel.md`](docs/cloudflare-tunnel.md): دسترسی امن از
  بیرون به داشبورد/API با Cloudflare Tunnel + Access، بدون باز کردن پورت
  روی سرور GPU‌دار (Cloudflare فقط برای دسترسی امن استفاده می‌شود، نه برای
  اجرای پایپ‌لاین سنگین که با GPU/Workers آن سازگار نیست).

### ریسک فنی اصلی: کیفیت TTS فارسی

XTTS v2 به‌صورت رسمی از فارسی پشتیبانی نمی‌کند و کیفیت Piper به صدای فارسی
جامعه‌محور استفاده‌شده بستگی دارد. قبل از سرمایه‌گذاری روی یک موتور، آن را روی
سیستم GPU‌دار خودتان تست کنید:

```bash
python scripts/tts_fa_poc.py --piper-voice /path/to/fa_IR-voice.onnx --try-xtts
```

خروجی‌ها در `scripts/tts_poc_output/` ذخیره می‌شوند. نتیجه را با
`TTS_ENGINE=piper|xtts` و `PIPER_FA_VOICE_PATH` در `.env` اعمال کنید
(`worker/tts_engines.py` هر دو موتور را پشت یک اینترفیس مشترک `TTSEngine`
پیاده‌سازی می‌کند).

### تست زنجیره روی یک ویدیوی نمونه (بدون Docker/Celery)

```bash
pip install -r requirements/worker-cpu.txt -r requirements/worker-gpu.txt
python scripts/run_pipeline_cli.py "https://www.youtube.com/watch?v=..." --whisper-model tiny
```

از مدل کوچک (`tiny`/`base`/`small`) برای تست سریع روی CPU استفاده کنید؛
`large-v3` برای رونویسی با کیفیت تولید روی GPU لازم است.

## جریان کار API

1. `POST /videos {"source_url": "..."}` → دانلود + رونویسی + تشخیص هایلایت را
   زنجیره می‌کند.
2. در داشبورد (تب «تایید کلیپ‌ها») کلیپ‌های پیشنهادی را مرور، ویرایش، یا تایید/رد کنید.
3. تایید یک `ClipCandidate` زنجیره برش→ری‌فریم→جداسازی صدا→ترجمه→دوبله→میکس→
   زیرنویس→رندر نهایی را برای همان کلیپ اجرا می‌کند.
4. خروجی نهایی و پیشنهاد کپشن/هشتگ در `storage/clips/<clip_id>/` قرار می‌گیرند.

## تست

```bash
pip install -r requirements/common.txt -r requirements/dev.txt
pytest
```

تست‌های موجود سبک هستند (فرمت SRT، ریاضیات crop برای ری‌فریم، پارس JSON خروجی
Claude) و بدون GPU/دیتابیس واقعی اجرا می‌شوند. تست end-to-end با مدل‌های سنگین
(faster-whisper `large-v3`، Demucs، TTS واقعی فارسی) نیازمند اجرا روی محیط
GPU‌دار است.

## ساختار ریپازیتوری

```
api/            FastAPI: routes, schemas
worker/         Celery app + یک ماژول به‌ازای هر مرحله پایپ‌لاین
models/         SQLAlchemy models + Alembic migrations
dashboard/      داشبورد Streamlit برای تایید/ویرایش کلیپ
scripts/        اسکریپت CLI خطی + POC کیفیت TTS فارسی
storage/        فایل‌های دانلودشده/میانی/خروجی (gitignored)
voice_models/   مدل‌های صدای Piper/XTTS دانلودشده روی هاست (gitignored)
tests/          تست‌های واحد سبک
```

## فاز ۶ — کارهای آینده (خارج از این نسخه)

- آپلود خودکار به شبکه‌های اجتماعی از طریق API رسمی هرکدام
- صف پردازش دسته‌ای (چند ویدیو هم‌زمان)
- انتخاب چند voice برای دوبله
- آنالیتیکس ساده روی کلیپ‌های تولیدشده
