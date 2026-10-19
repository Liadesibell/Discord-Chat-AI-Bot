import { useCallback, useEffect, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8080";

async function api(path, options = {}) {
  const { headers, ...requestOptions } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...requestOptions,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `İstek başarısız (${response.status}).`);
  }
  return payload;
}

function StatusPill({ online, children }) {
  return (
    <span className={`status-pill ${online ? "is-online" : "is-offline"}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}

function BrandLogo() {
  return (
    <span className="brand-logo brand-wordmark">
      <img src="/orlin-wordmark.png" alt="Orlin" />
    </span>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [guilds, setGuilds] = useState([]);
  const [selectedGuild, setSelectedGuild] = useState("");
  const [form, setForm] = useState(null);
  const [status, setStatus] = useState(null);
  const [inviteUrl, setInviteUrl] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const me = await api("/api/me");
      setUser(me.authenticated ? me : null);
      if (me.authenticated) {
        const [guildResult, statusResult, inviteResult] = await Promise.all([
          api("/api/guilds"),
          api("/api/status"),
          api("/api/invite"),
        ]);
        setGuilds(guildResult.guilds);
        setStatus(statusResult);
        setInviteUrl(inviteResult.url);
        setSelectedGuild((current) => {
          if (guildResult.guilds.some((guild) => guild.id === current)) {
            return current;
          }
          return guildResult.guilds[0]?.id || "";
        });
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const guild = guilds.find((item) => item.id === selectedGuild);
    if (!user || !selectedGuild || !guild?.can_manage) {
      setForm(null);
      return;
    }
    let active = true;
    api(`/api/guilds/${selectedGuild}/settings`)
      .then((settings) => {
        if (active) setForm(settings);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      });
    return () => {
      active = false;
    };
  }, [guilds, selectedGuild, user]);

  function updateForm(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
    setNotice("");
  }

  async function saveSettings(event) {
    event.preventDefault();
    if (!form || !selectedGuild) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api(`/api/guilds/${selectedGuild}/settings`, {
        method: "PUT",
        body: JSON.stringify({
          ...form,
          triggers: form.triggersText
            .split("\n")
            .map((trigger) => trigger.trim())
            .filter(Boolean),
        }),
      });
      setNotice("Sunucu ayarları kaydedildi.");
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
      setUser(null);
      setGuilds([]);
      setForm(null);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  if (loading) {
    return (
      <main className="loading-screen">
        <BrandLogo />
        <p>Orlin kontrol paneli hazırlanıyor…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="login-layout">
        <section className="login-card">
          <div className="brand-lockup">
            <BrandLogo />
          </div>
          <div className="eyebrow">ORLIN · DISCORD ASİSTANI</div>
          <h1>Sunucunuzda<br />düşünen bir yardımcı.</h1>
          <p className="muted">
            Orlin’i Discord sunucunuza ekleyin; yanıt davranışını ve
            tetikleyicileri bu panelden yönetin.
          </p>
          <a className="primary-button login-button" href={`${API_BASE}/auth/discord/login`}>
            Discord ile giriş yap <span aria-hidden="true">↗</span>
          </a>
          <div className="login-footnote">
            Giriş için Discord’da sunucuyu yönetme yetkisi gerekir.
          </div>
          {error && <div className="alert error-alert">{error}</div>}
        </section>
        <aside className="login-aside">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <div className="aside-copy">
            <div className="eyebrow">YEREL MODEL · UZMAN YÖNLENDİRMESİ</div>
            <h2>Doğru soruya,<br />doğru uzman.</h2>
            <p>
              Orlin, sohbet ve teknik soruları uygun uzman modele yönlendirerek
              her sunucuda tutarlı bir yardımcı deneyimi sunar.
            </p>
          </div>
          <div className="model-card">
            <span className="model-icon">✳</span>
            <div><strong>Orlin AI</strong><small>Flash · Reasoning · Coder</small></div>
            <span className="model-arrow">↗</span>
          </div>
        </aside>
      </main>
    );
  }

  const activeGuild = guilds.find((guild) => guild.id === selectedGuild);
  const botOnline = Boolean(status?.discord?.ready);
  const aiOnline = Boolean(status?.local_ai?.available);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand-lockup sidebar-brand" href="/">
          <BrandLogo />
          <span>ORLIN</span>
        </a>
        <div className="nav-label">ÇALIŞMA ALANI</div>
        <button className="nav-item active">
          <span className="nav-glyph">⌂</span> Genel bakış
        </button>
        <div className="nav-label server-label">SUNUCULARIM</div>
        <div className="guild-list">
          {guilds.map((guild) => (
            <button
              className={`guild-item ${selectedGuild === guild.id ? "selected" : ""}`}
              key={guild.id}
              onClick={() => {
                setSelectedGuild(guild.id);
                setNotice("");
              }}
              title={guild.name}
            >
              {guild.icon ? (
                <img src={guild.icon} alt="" className="guild-icon" />
              ) : (
                <span className="guild-initial">
                  {guild.name.slice(0, 1).toUpperCase()}
                </span>
              )}
              <span className="guild-name">{guild.name}</span>
              <span className="guild-status" />
            </button>
          ))}
          {!guilds.length && (
            <p className="sidebar-empty">Orlin’in katıldığı bir sunucu bulunamadı.</p>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="local-card">
            <span className="local-icon">⌁</span>
            <div><strong>Yerel Orlin modelleri</strong><small>{aiOnline ? "Router ve yanıt modeli hazır" : "Modelleri models klasörüne indirin"}</small></div>
            <span className={`mini-dot ${aiOnline ? "online" : ""}`} />
          </div>
          <button className="profile-row" onClick={logout}>
            <span className="profile-avatar">{user.username?.slice(0, 1).toUpperCase()}</span>
            <span className="profile-name">{user.username}</span>
            <span className="logout-symbol" title="Çıkış yap">↪</span>
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">Çalışma alanı <span>/</span> Genel bakış</div>
          <div className="topbar-actions">
            <StatusPill online={botOnline}>{botOnline ? "Bot çevrimiçi" : "Bot çevrimdışı"}</StatusPill>
            <button className="refresh-button" onClick={refresh} title="Durumu yenile">↻</button>
          </div>
        </header>

        <div className="content">
          {error && <div className="alert error-alert">{error}</div>}
          {notice && <div className="alert success-alert">{notice}</div>}

          <section className="welcome-row">
            <div>
              <div className="eyebrow">ORLIN KONTROL PANELİ</div>
              <h1>İyi günler, {user.username?.split(" ")[0]} <span>✦</span></h1>
              <p>Orlin’in Discord sunucularındaki davranışını buradan yönetin.</p>
            </div>
            {inviteUrl && (
              <a className="primary-button invite-button" href={inviteUrl} target="_blank" rel="noreferrer">
                <span>＋</span> Botu sunucuya ekle
              </a>
            )}
          </section>

          <section className="stat-grid">
            <article className="stat-card">
              <div className="stat-head"><span>Discord bağlantısı</span><span className="stat-glyph">◉</span></div>
              <div className="stat-value">{botOnline ? "Bağlı" : "Bekliyor"}</div>
              <div className="stat-foot">{status?.discord?.guild_count ?? 0} sunucuya katılmış</div>
            </article>
            <article className="stat-card">
              <div className="stat-head"><span>Yerel AI modelleri</span><span className="stat-glyph">✳</span></div>
              <div className="stat-value">{aiOnline ? "Hazır" : "Çevrimdışı"}</div>
              <div className="stat-foot">{aiOnline ? "Proje içindeki modeller kullanılabilir" : "Modelleri indirmek için başlatma yönergelerini izleyin"}</div>
            </article>
            <article className="stat-card">
              <div className="stat-head"><span>Yönetilebilir sunucu</span><span className="stat-glyph">⌘</span></div>
              <div className="stat-value">{guilds.length}</div>
              <div className="stat-foot">Discord yetkiniz olan sunucular</div>
            </article>
          </section>

          {activeGuild ? (
            <section className="settings-layout">
              <div className="settings-heading">
                <div className="guild-heading">
                  {activeGuild.icon ? (
                    <img src={activeGuild.icon} alt="" className="large-guild-icon" />
                  ) : (
                    <span className="large-guild-icon guild-initial">{activeGuild.name.slice(0, 1).toUpperCase()}</span>
                  )}
                  <div><div className="eyebrow">SUNUCU AYARLARI</div><h2>{activeGuild.name}</h2></div>
                </div>
                <StatusPill online={activeGuild.settings}>{activeGuild.settings ? "Asistan etkin" : "Asistan kapalı"}</StatusPill>
              </div>

              {!activeGuild.can_manage ? (
                <div className="settings-card read-only-card">
                  <div className="empty-symbol">⌑</div>
                  <h3>Bu sunucu salt okunur</h3>
                  <p>Sunucu ayarlarını değiştirmek için Discord hesabınızda Yönet sunucu veya Yönetici izni gerekir.</p>
                  <StatusPill online={activeGuild.settings}>{activeGuild.settings ? "Asistan etkin" : "Asistan kapalı"}</StatusPill>
                </div>
              ) : form ? (
                <form className="settings-card" onSubmit={saveSettings}>
                  <div className="section-title">
                    <div><h3>Yanıt davranışı</h3><p>Asistanın bu sunucuda ne zaman ve nasıl konuşacağını seçin.</p></div>
                  </div>

                  <label className="toggle-row">
                    <span className="toggle-copy"><strong>Asistanı etkinleştir</strong><small>Kapatıldığında bu sunucudaki mesajlara cevap verilmez.</small></span>
                    <input type="checkbox" checked={form.enabled} onChange={(event) => updateForm("enabled", event.target.checked)} />
                    <span className="toggle-switch" />
                  </label>
                  <label className="toggle-row">
                    <span className="toggle-copy"><strong>Etiketlenince yanıt ver</strong><small>Kullanıcılar botu @etiketlediğinde cevap oluşturur.</small></span>
                    <input type="checkbox" checked={form.respond_to_mentions} onChange={(event) => updateForm("respond_to_mentions", event.target.checked)} />
                    <span className="toggle-switch" />
                  </label>

                  <label className="field-label" htmlFor="triggers">Tetikleyici kelimeler <span>İsteğe bağlı</span></label>
                  <textarea
                    id="triggers"
                    className="text-input trigger-input"
                    value={form.triggersText ?? form.triggers.join("\n")}
                    onChange={(event) => updateForm("triggersText", event.target.value)}
                    placeholder={"yardım\nink"}
                    maxLength={1_300}
                    rows={3}
                  />
                  <div className="field-hint">Her satıra bir kelime veya kısa ifade yazın. Eşleşme büyük/küçük harfe duyarsızdır.</div>

                  <label className="field-label" htmlFor="model">Model seçimi</label>
                  <select id="model" className="text-input select-input" value={form.model} onChange={(event) => updateForm("model", event.target.value)}>
                    <option value="auto">Otomatik · Qwen 9B yönlendirici</option>
                    <option value="deepseek">DeepSeek R1 Pro · matematik, hata ve proje analizi</option>
                    <option value="qwen35b">Qwen 35B · karmaşık kodlama ve uzun bağlam</option>
                    <option value="gpt_oss">gpt-oss-20b · JSON, komut ve yapılandırılmış yanıt</option>
                    <option value="gemma4">Gemma 4 · günlük Türkçe sohbet ve özetleme</option>
                  </select>
                  <div className="field-hint">Otomatik seçim, mesajı proje içindeki Qwen 9B yönlendiriciyle sınıflandırır. Aynı anda yalnızca gereken yanıt modeli belleğe alınır.</div>

                  <label className="field-label" htmlFor="prompt">Asistan talimatları</label>
                  <textarea
                    id="prompt"
                    className="text-input prompt-input"
                    value={form.system_prompt}
                    onChange={(event) => updateForm("system_prompt", event.target.value)}
                    maxLength={3_000}
                    rows={5}
                  />
                  <div className="form-footer">
                    <span>Yalnızca bu sunucudaki yanıt tarzını etkiler.</span>
                    <button className="primary-button save-button" disabled={saving}>
                      {saving ? "Kaydediliyor…" : "Değişiklikleri kaydet"}
                    </button>
                  </div>
                </form>
              ) : (
                <div className="settings-card loading-settings">Sunucu ayarları yükleniyor…</div>
              )}
            </section>
          ) : (
            <section className="empty-state">
              <div className="empty-symbol">⌂</div>
              <h2>Henüz yönetilebilir sunucu yok</h2>
              <p>Botu bir Discord sunucusuna ekleyin ve o sunucuda Yönet sunucu iznine sahip hesabınızla giriş yapın.</p>
              {inviteUrl && <a className="primary-button" href={inviteUrl} target="_blank" rel="noreferrer">Botu sunucuya ekle ↗</a>}
            </section>
          )}

          <footer className="page-footer">
            <span>Orlin · Yerel model yönlendiricisiyle çalışır</span>
            <span>Sunucu ayarları bu bilgisayarda saklanır</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
