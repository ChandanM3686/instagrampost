"use client";
import { useState, useRef } from "react";
import Link from "next/link";

export default function Home() {
  const [postType, setPostType] = useState<"free" | "promo">("free");
  const [caption, setCaption] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const handleImage = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => setImagePreview(ev.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = () => {
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 4000);
  };

  const scrollToForm = () => {
    formRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* NAV */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        background: "rgba(10,10,15,0.8)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        padding: "0 40px", height: 70, display: "flex", alignItems: "center", justifyContent: "space-between"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10,
            background: "linear-gradient(135deg, #6c5ce7, #a29bfe)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, fontWeight: 900
          }}>S</div>
          <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5 }}>SPKR</span>
        </div>
        <div style={{ display: "flex", gap: 32, alignItems: "center" }}>
          <a href="#how" style={{ color: "var(--text-secondary)", textDecoration: "none", fontSize: 14, fontWeight: 500, transition: "color 0.2s" }}>How It Works</a>
          <a href="#pricing" style={{ color: "var(--text-secondary)", textDecoration: "none", fontSize: 14, fontWeight: 500 }}>Pricing</a>
          <Link href="/admin" style={{ color: "var(--text-secondary)", textDecoration: "none", fontSize: 14, fontWeight: 500 }}>Admin</Link>
          <button onClick={scrollToForm} className="btn-primary btn-sm">Submit Post</button>
        </div>
      </nav>

      {/* HERO */}
      <section style={{
        minHeight: "100vh", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", textAlign: "center",
        padding: "120px 20px 80px",
        background: "radial-gradient(ellipse at 50% 0%, rgba(108,92,231,0.15) 0%, transparent 60%), radial-gradient(ellipse at 80% 80%, rgba(0,184,148,0.08) 0%, transparent 50%)",
        position: "relative", overflow: "hidden"
      }}>
        {/* Floating orbs */}
        <div style={{
          position: "absolute", width: 400, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(108,92,231,0.08), transparent 70%)",
          top: -100, right: -100, animation: "float 8s ease-in-out infinite"
        }} />
        <div style={{
          position: "absolute", width: 300, height: 300, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(0,184,148,0.06), transparent 70%)",
          bottom: -50, left: -50, animation: "float 6s ease-in-out infinite 2s"
        }} />

        <div className="animate-fade-in-up" style={{ position: "relative", zIndex: 1 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "rgba(108,92,231,0.1)", border: "1px solid rgba(108,92,231,0.2)",
            borderRadius: 30, padding: "8px 20px", marginBottom: 32, fontSize: 13, fontWeight: 500, color: "var(--accent-light)"
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)", animation: "pulse-glow 2s infinite" }} />
            Live — Posts going out daily
          </div>
          <h1 style={{
            fontSize: "clamp(42px, 6vw, 80px)", fontWeight: 900, lineHeight: 1.05,
            letterSpacing: -2, marginBottom: 24,
            background: "linear-gradient(135deg, #fff 0%, #a29bfe 50%, #55efc4 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"
          }}>
            Speak Your Mind.<br />We Post It.
          </h1>
          <p style={{
            fontSize: 18, color: "var(--text-secondary)", maxWidth: 540,
            margin: "0 auto 40px", lineHeight: 1.7
          }}>
            Submit your content anonymously. We publish it on Instagram.
            Free posts or promoted — your voice, amplified.
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            <button onClick={scrollToForm} className="btn-primary" style={{ padding: "16px 36px", fontSize: 16 }}>
              ✍️ Submit a Post
            </button>
            <a href="#how" className="btn-secondary" style={{ padding: "16px 36px", fontSize: 16 }}>
              Learn More →
            </a>
          </div>

          {/* Stats */}
          <div style={{
            display: "flex", gap: 48, justifyContent: "center", marginTop: 64,
            flexWrap: "wrap"
          }}>
            {[
              { num: "2,847", label: "Posts Published" },
              { num: "14.2K", label: "Followers" },
              { num: "98%", label: "Approval Rate" },
            ].map((s, i) => (
              <div key={i} className="animate-fade-in-up" style={{ animationDelay: `${i * 0.15}s` }}>
                <div style={{ fontSize: 36, fontWeight: 800, color: "var(--text-primary)" }}>{s.num}</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" style={{ padding: "100px 40px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <h2 style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1, marginBottom: 12 }}>How It Works</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: 16 }}>Three simple steps to get your voice heard</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
          {[
            { icon: "📝", title: "Write Your Post", desc: "Upload an image, write your caption. Stay anonymous or add your name." },
            { icon: "🛡️", title: "Content Review", desc: "Our AI filters check for harmful content. Admins approve quality posts." },
            { icon: "📸", title: "Published on Instagram", desc: "Your post goes live on our Instagram page for thousands to see." },
          ].map((item, i) => (
            <div key={i} className="glass-card animate-fade-in-up" style={{
              padding: 36, textAlign: "center", animationDelay: `${i * 0.15}s`,
              transition: "all 0.3s ease", cursor: "default",
              position: "relative", overflow: "hidden"
            }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.transform = "translateY(-6px)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--glass-border)"; e.currentTarget.style.transform = "translateY(0)"; }}
            >
              <div style={{
                position: "absolute", top: 0, left: 0, right: 0, height: 3,
                background: "var(--gradient-1)", opacity: 0, transition: "opacity 0.3s"
              }} />
              <div style={{
                width: 64, height: 64, borderRadius: 16, margin: "0 auto 20px",
                background: "rgba(108,92,231,0.1)", display: "flex", alignItems: "center",
                justifyContent: "center", fontSize: 28
              }}>{item.icon}</div>
              <div style={{
                fontSize: 11, fontWeight: 700, color: "var(--accent-light)",
                textTransform: "uppercase", letterSpacing: 2, marginBottom: 12
              }}>Step {i + 1}</div>
              <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>{item.title}</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: 14, lineHeight: 1.7 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SUBMIT FORM */}
      <section ref={formRef} id="submit" style={{
        padding: "100px 40px", maxWidth: 700, margin: "0 auto"
      }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h2 style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1, marginBottom: 12 }}>Submit Your Post</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: 16 }}>Your content, published anonymously on Instagram</p>
        </div>

        <div className="glass-card" style={{ padding: 40 }}>
          {/* Post Type Toggle */}
          <div style={{
            display: "flex", background: "var(--bg-secondary)", borderRadius: 12,
            padding: 4, marginBottom: 32
          }}>
            {(["free", "promo"] as const).map((type) => (
              <button key={type} onClick={() => setPostType(type)} style={{
                flex: 1, padding: "14px 20px", borderRadius: 10, border: "none",
                fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: 14,
                cursor: "pointer", transition: "all 0.3s ease",
                background: postType === type
                  ? (type === "free" ? "var(--gradient-2)" : "var(--gradient-1)")
                  : "transparent",
                color: postType === type ? "white" : "var(--text-muted)"
              }}>
                {type === "free" ? "🆓 Free Post" : "⭐ Promoted Post — $1-$2"}
              </button>
            ))}
          </div>

          {postType === "promo" && (
            <div className="animate-fade-in" style={{
              background: "rgba(108,92,231,0.08)", border: "1px solid rgba(108,92,231,0.15)",
              borderRadius: 12, padding: 20, marginBottom: 28, display: "flex", gap: 12, alignItems: "flex-start"
            }}>
              <span style={{ fontSize: 20 }}>💎</span>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 14 }}>Promoted posts get priority</div>
                <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>
                  Your post will be published faster with a &quot;Promoted&quot; badge. Payment via Stripe. $1 for image, $2 for video.
                </div>
              </div>
            </div>
          )}

          {/* Image Upload */}
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
              📎 Image / Video *
            </label>
            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: "2px dashed var(--glass-border)", borderRadius: 16,
                padding: imagePreview ? 0 : "48px 24px", textAlign: "center",
                cursor: "pointer", transition: "all 0.3s ease",
                overflow: "hidden", position: "relative",
                minHeight: imagePreview ? "auto" : 180
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--glass-border)"; }}
            >
              {imagePreview ? (
                <div style={{ position: "relative" }}>
                  <img src={imagePreview} alt="Preview" style={{ width: "100%", display: "block", borderRadius: 14 }} />
                  <button onClick={(e) => { e.stopPropagation(); setImagePreview(null); }} style={{
                    position: "absolute", top: 12, right: 12, width: 32, height: 32,
                    borderRadius: "50%", background: "rgba(0,0,0,0.7)", border: "none",
                    color: "white", cursor: "pointer", fontSize: 16, display: "flex",
                    alignItems: "center", justifyContent: "center"
                  }}>×</button>
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 42, marginBottom: 12, opacity: 0.4 }}>📷</div>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Click to upload image or video</div>
                  <div style={{ color: "var(--text-muted)", fontSize: 13 }}>JPEG, PNG, MP4 — Max 10MB</div>
                </>
              )}
              <input ref={fileRef} type="file" accept="image/*,video/*" onChange={handleImage} style={{ display: "none" }} />
            </div>
          </div>

          {/* Caption */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>✏️ Caption *</label>
              <span style={{ fontSize: 12, color: charCount > 2000 ? "var(--red)" : "var(--text-muted)" }}>
                {charCount}/2200
              </span>
            </div>
            <textarea
              className="input-field"
              placeholder="Write your anonymous message here... Speak your mind!"
              value={caption}
              onChange={(e) => { setCaption(e.target.value); setCharCount(e.target.value.length); }}
              style={{ minHeight: 140 }}
            />
          </div>

          {/* Optional name */}
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
              👤 Display Name <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(optional)</span>
            </label>
            <input className="input-field" placeholder="Leave blank for anonymous submission" />
          </div>

          {/* reCAPTCHA placeholder */}
          <div style={{
            background: "var(--bg-secondary)", borderRadius: 12, padding: 16,
            marginBottom: 28, display: "flex", alignItems: "center", gap: 14
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6, border: "2px solid var(--glass-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", transition: "all 0.2s"
            }}>
              <span style={{ color: "var(--green)", fontSize: 16 }}>✓</span>
            </div>
            <span style={{ fontSize: 14 }}>I&apos;m not a robot</span>
            <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-muted)" }}>reCAPTCHA</span>
          </div>

          <button onClick={handleSubmit} className="btn-primary" style={{
            width: "100%", justifyContent: "center", padding: "16px 24px", fontSize: 16
          }}>
            {postType === "promo" ? "💳 Pay & Submit Post" : "🚀 Submit Post for Free"}
          </button>

          <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-muted)", marginTop: 16 }}>
            All submissions are reviewed. Harmful or offensive content will be rejected.
          </p>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" style={{ padding: "100px 40px", maxWidth: 900, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <h2 style={{ fontSize: 40, fontWeight: 800, letterSpacing: -1, marginBottom: 12 }}>Simple Pricing</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: 16 }}>Free for everyone. Promote for more reach.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
          {/* Free */}
          <div className="glass-card" style={{ padding: 40 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--green)", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 16 }}>Free</div>
            <div style={{ fontSize: 48, fontWeight: 900, marginBottom: 8 }}>$0</div>
            <div style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 32 }}>per post</div>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 16, marginBottom: 36 }}>
              {["Image + caption post", "Anonymous submission", "Content moderation", "Standard queue"].map((f, i) => (
                <li key={i} style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14, color: "var(--text-secondary)" }}>
                  <span style={{ color: "var(--green)" }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button onClick={scrollToForm} className="btn-secondary" style={{ width: "100%", justifyContent: "center" }}>
              Submit Free Post
            </button>
          </div>
          {/* Promo */}
          <div style={{
            background: "linear-gradient(135deg, rgba(108,92,231,0.12), rgba(162,155,254,0.05))",
            border: "1px solid rgba(108,92,231,0.3)", borderRadius: "var(--radius)",
            padding: 40, position: "relative", overflow: "hidden"
          }}>
            <div style={{
              position: "absolute", top: 16, right: 16,
              background: "var(--gradient-1)", borderRadius: 20,
              padding: "4px 14px", fontSize: 11, fontWeight: 700, color: "white"
            }}>POPULAR</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--accent-light)", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 16 }}>Promoted</div>
            <div style={{ fontSize: 48, fontWeight: 900, marginBottom: 8 }}>$1<span style={{ fontSize: 20, color: "var(--text-muted)" }}>-$2</span></div>
            <div style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 32 }}>per post</div>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 16, marginBottom: 36 }}>
              {["Everything in Free", "Priority publishing", "⭐ Promoted badge", "Video posts ($2)", "Faster approval", "Payment via Stripe"].map((f, i) => (
                <li key={i} style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14, color: "var(--text-secondary)" }}>
                  <span style={{ color: "var(--accent-light)" }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button onClick={() => { setPostType("promo"); scrollToForm(); }} className="btn-primary" style={{ width: "100%", justifyContent: "center" }}>
              ⭐ Submit Promoted Post
            </button>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{
        borderTop: "1px solid var(--glass-border)", padding: "40px",
        textAlign: "center", color: "var(--text-muted)", fontSize: 13
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 12 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: "var(--gradient-1)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 13, fontWeight: 900, color: "white"
          }}>S</div>
          <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>SPKR</span>
        </div>
        © 2026 SPKR. All rights reserved. Built with ❤️
      </footer>

      {/* TOAST */}
      {submitted && (
        <div className="toast toast-success">
          ✅ Post submitted successfully! It will be reviewed shortly.
        </div>
      )}
    </div>
  );
}
