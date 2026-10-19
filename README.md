# Orlin Discord Asistanı

Orlin, markanızın logosunu kullanan Discord asistanı ve React tabanlı yerel
kontrol panelidir. Discord'da mesajda adı geçtiğinde, bot etiketlendiğinde veya sunucu yöneticisinin
belirlediği ek tetikleyiciler kullanıldığında yanıt verir. Her sunucunun ayarları
ayrı ayrı bu bilgisayardaki SQLite veritabanında tutulur.
Web panelinde, arka planı şeffaf ve marka yazısını da içeren Orlin wordmark
kullanılır; tarayıcı ikonu aynı logonun ambleminden oluşturulur.

## Donanım ve model

Bu bilgisayarda ölçülen bellek yaklaşık 16 GB RAM ve 8 GB ekran kartı belleğidir.
Bot, model ağırlıklarını ve yerel çıkarım kodunu **bu Discord bot projesinin**
`models` klasöründen ve Python ortamından kullanır. Başka bir `Ink AI` projesine,
servisine veya API'sine bağlanmaz. İndirme yaklaşık 53 GB disk alanı gerektirir.

| Model | Rol ve yönlendirme amacı | GGUF dosya boyutu |
|---|---|---:|
| Qwen3.5-9B | Her otomatik isteği sınıflandıran model yönlendirici; tek başına yanıt modeli değildir | 5.7 GB |
| DeepSeek-R1-Distill-Qwen-14B | Çok adımlı matematik, derin analiz, hata ayıklama, kök neden ve büyük proje incelemesi | 9.0 GB |
| Qwen3.5-35B-A3B | Uzun bağlam, karmaşık teknik sorular, kod yazımı ve ileri teknik destek | 22.0 GB |
| gpt-oss-20b | JSON/şema, yapılandırılmış komutlar, moderasyon ve talimat takibi | 11.6 GB |
| Gemma 4 E4B | Günlük sohbet, Türkçe diyalog, özet ve metin düzenleme; hata durumunda yedek | 5.0 GB |

DeepSeek dosyası, tam 671B DeepSeek-R1 değil; yerel çalıştırmaya uygun 14B
DeepSeek-R1 distil modelidir. Aynı anda tek model belleğe alınır. 35B modelin
dosyası bilgisayardaki RAM ve GPU belleğinden büyük olduğundan disk sayfalaması
nedeniyle çok yavaş çalışabilir veya yüklenemeyebilir. Router uzman modeli
yükleyemezse Gemma 4'ü, o da başarısız olursa 9B modeli yedek olarak dener.
Model yanıtlarının kusursuz olacağı garanti edilemez; kritik sonuçları doğrulayın.

## Gerekenler

- Windows 10/11, Python 3.12+, `uv`, Node.js/npm
- Discord Developer Portal'da oluşturulmuş bot uygulaması

## Kurulum

Proje klasöründe PowerShell açın:

```powershell
uv sync
Copy-Item .env.example .env
```

`uv sync`, Discord bot projesinin kendi sanal ortamına Vulkan GPU desteği olan
`llama-cpp-python` paketini kurar. Modeller bu projenin `models` dizinine indirilir:

```powershell
uv run python scripts\download_model.py
```

İlk indirme yaklaşık 53 GB'dir. Her dosyanın boyutu doğrulanır; kesintiden sonra
komutu yeniden çalıştırmak tamamlanmış modelleri tekrar indirmez.

Proje kökünde hazır bulunan `.env` dosyasına Discord Developer Portal'dan
alınan değerleri girin:

- `DISCORD_BOT_TOKEN`: Developer Portal → **Bot** → **Reset Token** ile alınır.
- `DISCORD_CLIENT_ID`: **General Information** sayfasındaki Application ID.
- `DISCORD_CLIENT_SECRET`: **OAuth2** sayfasındaki Client Secret.
- `DISCORD_REDIRECT_URI`: OAuth2 → Redirects bölümüne de aynı adres eklenmeli:
  `http://127.0.0.1:8080/auth/discord/callback`.

`.env` gizli bilgileri içerir; bot token'ını veya Client Secret'ı kimseyle
paylaşmayın. Hazır `WEB_SESSION_SECRET` değerini değiştirmek isterseniz yeni
bir tane üretin:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Developer Portal'da **Bot → Privileged Gateway Intents** bölümünden
**Message Content Intent** seçeneğini etkinleştirin. OAuth2 Redirect URL olarak
`http://127.0.0.1:8080/auth/discord/callback` ekleyin. `.env` dosyasını
kaydedip backend'i başlatın; paneli açıp Discord ile giriş yaptıktan sonra
**Botu sunucuya ekle** düğmesini kullanın. Alternatif olarak Developer Portal →
OAuth2 → URL Generator'da `bot` kapsamını ve View Channels, Send Messages,
Read Message History izinlerini seçerek davet bağlantısı oluşturabilirsiniz.
Kullanıcılar, panelde ayar yapabilmek için Discord OAuth ekranından
geçer. Botun kullanıcının hesabında bulunduğu tüm sunucuları listelenir;
`Manage Server` veya `Administrator` izni olmayan sunucular salt okunur görünür.
Yalnızca gerekli izne sahip olduğunuz sunucuların ayarları değiştirilebilir.

Web paneli bağımlılıklarını kurun:

```powershell
Set-Location frontend
npm.cmd install
Set-Location ..
```

## Çalıştırma

Yerel model çıkarımı Discord bot backend'inin içinde çalışır; ayrı AI projesi
veya ikinci bir model sunucusu başlatılmaz. Önce backend'i çalıştırın:

```powershell
.\scripts\start-backend.cmd
```

Backend varsayılan olarak yerel modelleri kullanır; model dosyaları yoksa önce
indirme komutunu çalıştırın. Otomatik yönlendirme 9B ile sınıflandırır, ardından
yalnızca seçilen uzman modelini yükler. GPU belleğini korumak için router ile
uzman model aynı anda bellekte tutulmaz; bu nedenle otomatik isteklerde model
değişimi yanıt süresini uzatabilir.

Dashboard için ikinci pencerede:

```powershell
.\scripts\start-dashboard.cmd
```

Panel: `http://127.0.0.1:5173`. Discord bot API/panel sunucusu
`127.0.0.1:8080` üzerinde çalışır. Bot token'ı
yoksa web API yine çalışır; durum kartında bot bağlantısı hazır görünmez.

## Bot davranışı

- Mesaj içinde `Orlin` adı geçtiğinde veya bot etiketlendiğinde komutsuz yanıt verir.
- Tetiklenen mesajdan önceki kanal konuşmalarını bağlam olarak alır; varsayılan
  `auto` ayarında Qwen 9B isteği sınıflandırır ve uygun uzman model yanıtlar.
- Kullanıcı açıkça “web'de ara”, “web taraması yap” gibi bir istek yazarsa
  Bing RSS üzerinden arama yapar, sonuç özetlerini modele verir ve yanıtın
  sonuna kaynak bağlantılarını ekler. Arama sorgusu Bing'e gönderilir; arama
  istenmemiş normal sohbette web isteği yapılmaz.
- Panelde satır başına bir tetikleyici ekleyerek ek yanıt koşulları belirlenebilir.
- Otomatik router; matematik, kök neden/hata ve proje incelemesini DeepSeek'e;
  karmaşık kodlama ve teknik desteği Qwen'e; JSON, komut ve moderasyon isteklerini
  gpt-oss'a; günlük sohbeti Gemma'ya yönlendirir. Kararsız sınıflandırmada Gemma seçilir.
- Yanıt oluşturulurken kanaldaki önceki 10 metin mesajı bağlam olarak kullanılır;
  yerel model belleği aşılmasın diye bağlam modelin token sınırına göre daraltılır.
- Bot cevaplarını kullanıcı başına 5 saniyeyle sınırlar ve model üretimini sıraya alır.
- gpt-oss istekleri araç/komut/JSON biçiminde düzenleyebilir; botta gerçekten
  tanımlanmamış araçlar çalıştırılmaz ve Discord sunucu yönetim yetkisi verilmez.
  Harici API entegrasyonları kurulu değildir. İnternet araması yalnızca
  kullanıcı açıkça istediğinde yapılır; diğer yanıtlar yerel modellere ve
  Discord'daki mevcut konuşma bağlamına dayanır.
- Bot yanıtı uzun olduğunda Discord mesaj sınırına uygun parçalara ayırır ve
  cevap içindeki mention'ların başka kullanıcıları bildirimle rahatsız etmesini engeller.
- Sunucu ayarları `data/bot.sqlite3` dosyasına yazılır. Konuşma geçmişi
  saklanmaz; her yanıt için son mesajlar Discord kanalından alınır.

## Güvenlik ve sınırlar

- API'ler varsayılan olarak yalnızca `127.0.0.1` üzerinde dinler. Bu paneli
  genel internete açmayın; internete açmak için TLS, güvenli oturum çerezleri,
  CSRF koruması ve kimlik doğrulama dağıtım ayarlarının ayrıca yapılandırılması gerekir.
- Discord token'ı, OAuth secret ve oturum anahtarı `.env` içinde yer almalı ve
  hiçbir zaman depoya eklenmemelidir.
- Discord mesaj içeriği bu projedeki yerel GGUF modeline gönderilir. İndirme
  tamamlandıktan sonra çıkarım için harici bir model API'si kullanılmaz.
- Botu çok sayıda Discord sunucusunda barındırmadan önce Discord'un bot,
  gizlilik, veri işleme ve intent gereksinimlerini inceleyin.

## Test

```powershell
uv run pytest
Set-Location frontend
npm.cmd run build
```
