# Inbound plan: make the clinics message YOU first

WhatsApp allows replying freely once someone writes to you (24-hour window), and Meta's **Click-to-WhatsApp ads** exist exactly for this. After the first inbound message everything below can be automated or semi-automated with no policy risk. This replaces cold first messages; keep the paced `send_queue.py` only as a small manual extra (10–15/day).

---

## 1. Click-to-WhatsApp ad (one-time setup, ~30 min on your side)

**Goal:** a dentist/clinic owner in Lima taps the ad and a WhatsApp chat opens to your Business number with a pre-filled message.

**Audience (B2B):** Lima Metropolitana · age 28–60 · interests/job titles related to *Odontología / Dentista / Clínica dental* · Spanish. (Meta's targeting options change; pick the closest "Dentists / Dentistry" options available.)

**Format & placement:** start with 1 image + 1 short vertical video (your 30-s demo), Facebook + Instagram feeds/Reels. Objective: **Messages → WhatsApp**.

**Pre-filled message:** `Hola, quiero la auditoría gratis de mi consultorio 🦷`

### 3 headline tests (book: test the headline first, 5× more people read it than anything else)
| # | Headline | Primary text |
|---|---|---|
| A | **Tu consultorio no sale en Google** | Dentistas de Lima: si buscan "dentista en [tu distrito]" y no apareces con tu propia web, esos pacientes se van con otro. Te hago una auditoría gratis de tu ficha de Google y un borrador de tu web. Toca "Enviar mensaje". |
| B | **Web para tu clínica en 7 días** | Página profesional con botón de WhatsApp, Google Maps y citas. Si no está lista en 7 días, no pagas. Esta semana tomo solo 5 consultorios. |
| C | **¿Cuántos pacientes pierdes sin web?** | Te enseño en 3 minutos qué te falta para recibir más pacientes por WhatsApp. Gratis y sin compromiso. |

Keep the winner, replace the loser, repeat weekly.

### Budget (reverse it from your goal, like the book says)
Placeholders to replace with your real numbers after week 1:
`ad spend/month = target clients × (1 ÷ close rate) × (calls per client) × cost per conversation`
Example only: 3 clients/month ÷ 0.33 close = 9 sales conversations; if 1 in 3 chats becomes one → 27 chats; at S/ 8 per chat ≈ **S/ 216/month**. Start with a **small daily budget (S/ 15–25)** for 7 days, read the real cost per chat in Ads Manager, then scale or stop. (The S/ 8 is a guess, not data.)

---

## 2. WhatsApp Business app setup (so replies are fast and human)
- **Profile:** name "TuNombre · Páginas web para clínicas dentales", logo, description, address/district, hours, link to your demo.
- **Greeting message** (auto, first contact):
  > ¡Hola! 👋 Gracias por escribir. Soy [TU NOMBRE], hago páginas web para consultorios dentales. Cuéntame: ¿cómo se llama tu consultorio y en qué distrito está? Con eso te preparo tu mini auditoría gratis (3 puntos para atraer más pacientes).
- **Away message** (outside hours): `Gracias por escribir 🙌 Te respondo mañana a primera hora (9:00–18:00, lun–sáb).`
- **Quick replies** (type `/` in a chat): `/auditoria`, `/demo`, `/precio`, `/garantia`, `/agendar`, using the texts in `scripts-es.md` sections A, D and E.
- **Labels:** Nuevo · Auditoría enviada · Llamada agendada · Cliente · No interesado.

---

## 3. Reply playbook (what happens after they write)
1. **Within minutes** (greeting does it) → they send clinic name + district.
2. **You (or an assistant) reply with the audit** (3 concrete findings from their Maps listing; a mockup of their homepage if time allows) + CTA "¿Te lo muestro en una llamada de 10 min hoy a las 4 o mañana a las 11?"
3. Objections → `scripts-es.md` section D. Close → section E. After delivery → ask for the referral and testimonial.
4. **No answer after the audit:** one follow-up next day, one in 4 days (inside the 24h window rules for free-form messages; after 24h only approved templates via the Business API, or a manual message from the Business app).

## 4. What I can automate for you after the first inbound message
- Draft each audit from the clinic's Maps data (`leads_clean.csv` already has rating, reviews, district, "no website").
- Draft replies to each incoming message if you paste/forward them here.
- A reply assistant on the **official WhatsApp Business Platform** (Cloud API) for *inbound* chats. It needs a Meta developer app, a verified business and a hosted webhook, which means a one-time setup with your Meta account. I can write the webhook and the reply logic when you're ready; it can't be done without your Meta login.

## 5. Organic inbound (free, in parallel)
Daily short video on Facebook/Instagram/TikTok with the CTA **"Comenta AUDITORÍA"** → reply by DM/WhatsApp (people who comment are consenting to be contacted). Hooks are in `scripts-es.md` section B.
