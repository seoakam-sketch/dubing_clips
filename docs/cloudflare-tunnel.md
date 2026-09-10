# دسترسی امن به داشبورد/API از طریق Cloudflare Tunnel

## چرا این‌طور و نه چیز دیگر

پایپ‌لاین این پروژه (`faster-whisper large-v3`, Demucs, XTTS/Piper, رندر
طولانی با ffmpeg) به GPU و اجرای طولانی نیاز دارد؛ Cloudflare Workers/Pages
(بدون GPU، محدودیت زمان اجرا، بدون دیسک پایدار دلخواه) برای این نوع بار
مناسب نیستند. بنابراین **سرور واقعی (GPU‌دار) همچنان همان ماشینی است که
`docker-compose.yml` را اجرا می‌کند** — چه سرور شخصی، چه یک VPS/سرور
GPU‌دار. نقش Cloudflare اینجا فقط **دسترسی امن از بیرون** به داشبورد
Streamlit (و در صورت نیاز API) است، بدون باز کردن هیچ پورت ورودی روی آن
سرور و بدون IP عمومی ثابت.

Cloudflare Tunnel یک کانکشن خروجی از سرور شما به شبکه Cloudflare برقرار
می‌کند؛ ترافیک از `https://<hostname-دلخواه>.<دامنه‌شما>` وارد Cloudflare
شده و از همان تونل به سرویس داخلی (`dashboard:8501` یا `api:8000`) هدایت
می‌شود. با Cloudflare Access می‌توانید لاگین (ایمیل/GitHub/...) را هم جلوی
آن اجباری کنید — چون این ابزار شخصی است و نباید عمومی در دسترس باشد.

## پیش‌نیاز

- یک دامنه که در Cloudflare مدیریت می‌شود (روی Cloudflare DNS باشد).
- دسترسی به [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/).

## مرحله ۱: ساخت Tunnel در Zero Trust Dashboard

1. وارد **Zero Trust → Networks → Tunnels** شوید.
2. **Create a tunnel** → نوع را **Cloudflared** انتخاب کنید → یک نام بدهید
   (مثلاً `clipdub`).
3. در صفحه بعد یک دستور نصب/توکن نمایش داده می‌شود؛ فقط به **توکن** نیاز
   دارید (رشته طولانی بعد از `--token`). آن را کپی کنید.
4. در همان صفحه، بخش **Public Hostname** را برای هر سرویس اضافه کنید:
   - Hostname: `dashboard.example.com` → Service: `http://dashboard:8501`
   - (اختیاری) Hostname: `api.example.com` → Service: `http://api:8000`

   نکته: `dashboard` و `api` اینجا **نام سرویس‌ها در همان
   `docker-compose.yml`** هستند، نه IP — چون کانتینر `cloudflared` روی همان
   شبکه Docker Compose بالا می‌آید و این نام‌ها را resolve می‌کند.

## مرحله ۲: افزودن Access Policy (احراز هویت)

چون این ابزار شخصی/داخلی است، توصیه می‌شود قبل از عمومی‌کردن هاست‌نیم، یک
Access Application برایش بسازید:

1. **Zero Trust → Access → Applications → Add an application → Self-hosted**
2. دامنه‌ای که در مرحله قبل ساختید (`dashboard.example.com`) را انتخاب کنید.
3. یک Policy با Include: `Emails` → فقط ایمیل خودتان (یا چند نفر مشخص) اضافه
   کنید. بدون این مرحله، هر کسی که هاست‌نیم را حدس بزند به داشبورد شما
   (و از آنجا به کل پایپ‌لاین) دسترسی خواهد داشت.

## مرحله ۳: اتصال توکن به Docker Compose

در `.env`:
```
CLOUDFLARE_TUNNEL_TOKEN=<توکنی که در مرحله ۱ کپی کردید>
```

سرویس `cloudflared` در `docker-compose.yml` پشت یک Compose **profile** به
نام `cloudflare` است تا در اجرای معمولی (بدون تنظیم Cloudflare) تلاش نکند
بدون توکن بالا بیاید:

```bash
docker compose --profile cloudflare up -d cloudflared
# یا برای بالا آوردن همه‌چیز با هم:
docker compose --profile cloudflare up --build -d
```

بررسی سلامت تونل:
```bash
docker compose logs -f cloudflared
```
باید خطوطی شبیه `Registered tunnel connection` ببینید. بعد از آن،
`https://dashboard.example.com` باید (بعد از لاگین Access) داشبورد را نشان
دهد.

## نکات امنیتی

- هرگز پورت‌های `8000`/`8501`/`5432`/`6379` را مستقیم روی فایروال سرور به
  اینترنت باز نکنید؛ کل هدف Tunnel این است که این کار لازم نباشد. اگر سرور
  شما در شبکه‌ای با IP عمومی است، این پورت‌ها را در `docker-compose.yml`
  فقط برای دسترسی محلی (`127.0.0.1:8501:8501`) نگه دارید یا کامل حذف کنید
  و صرفاً از طریق Tunnel به آن‌ها برسید.
- `CLOUDFLARE_TUNNEL_TOKEN` را مثل هر سکرت دیگری در `.env` نگه دارید (که در
  `.gitignore` است) — هرگز commit نکنید.
- اگر روزی خواستید API را هم از بیرون در دسترس بگذارید (مثلاً برای یک
  فرانت جدا)، حتماً پشت همان Access Application یا یک Application جدا با
  Policy مشخص بگذارید — API فعلاً authentication خودش را ندارد.
