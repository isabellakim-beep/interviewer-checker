'use client'

import { useRef } from 'react'
import styles from './page.module.css'

const GOOGLE_FORM_URL = 'https://forms.gle/EbvE1ygBHeytYjGj8'

const highlights = [
  {
    icon: '🏢',
    title: 'Office Tour',
    desc: "Get a behind-the-scenes look at Sendbird's Seoul headquarters on the 16th floor of Seonneung-ro.",
  },
  {
    icon: '💼',
    title: 'Internship Opportunities',
    desc: 'Discover open internship positions and hear directly from the team about life at Sendbird.',
  },
  {
    icon: '🤝',
    title: 'Network with Sendbirdians',
    desc: 'Meet engineers, product managers, and designers in a casual, welcoming environment.',
  },
]

const agenda = [
  { time: '6:00 PM', title: 'Welcome & Check-in', desc: 'Arrive, grab a drink, and get settled in' },
  { time: '6:15 PM', title: 'Office Tour', desc: "Explore Sendbird's Seoul headquarters on the 16th floor" },
  {
    time: '6:45 PM',
    title: 'Internship Opportunities',
    desc: "Learn about open internship roles and what it's like to work at Sendbird",
  },
  {
    time: '7:30 PM',
    title: 'Networking',
    desc: 'Connect one-on-one with Sendbirdians — engineers, designers, PMs, and more',
  },
  { time: '8:00 PM', title: 'See You Again', desc: 'Wrap up and exchange contacts' },
]

export default function Home() {
  const registerRef = useRef<HTMLElement>(null)

  const scrollToRegister = () => {
    registerRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <main className={styles.main}>
      {/* ── Hero ── */}
      <section className={styles.hero}>
        <div className={styles.heroGlow} />
        <div className={styles.heroContent}>
          {/* Logos */}
          <div className={styles.logos}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/sendbird-logo.png" alt="Sendbird" height={32} className={styles.logo} />
            <span className={styles.logoDivider}>×</span>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/delight-logo.png" alt="delight.ai" height={28} className={styles.logo} />
          </div>

          <div className={styles.badge}>College Student OpenHouse</div>

          <h1 className={styles.heroTitle}>
            2026 Sendbird
            <br />
            OpenHouse
          </h1>

          <p className={styles.heroSub}>
            Visit our Seoul office, discover internship opportunities,
            <br />
            and connect with the Sendbird team.
          </p>

          <div className={styles.eventMeta}>
            <div className={styles.metaItem}>
              <span>📅</span>
              <span>June 18, 2026</span>
            </div>
            <div className={styles.metaDot} />
            <div className={styles.metaItem}>
              <span>🕕</span>
              <span>6:00 – 8:00 PM KST</span>
            </div>
            <div className={styles.metaDot} />
            <div className={styles.metaItem}>
              <span>📍</span>
              <span>Sendbird Seoul, 16F</span>
            </div>
          </div>

          <button className={styles.ctaButton} onClick={scrollToRegister}>
            Register Now
          </button>
        </div>
      </section>

      {/* ── What to Expect ── */}
      <section className={styles.section}>
        <div className={styles.container}>
          <h2 className={styles.sectionTitle}>What to Expect</h2>
          <div className={styles.cards}>
            {highlights.map((h) => (
              <div key={h.title} className={styles.card}>
                <div className={styles.cardIcon}>{h.icon}</div>
                <h3 className={styles.cardTitle}>{h.title}</h3>
                <p className={styles.cardDesc}>{h.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Agenda ── */}
      <section className={styles.section}>
        <div className={styles.container}>
          <h2 className={styles.sectionTitle}>Agenda</h2>
          <div className={styles.timeline}>
            {agenda.map((item, i) => (
              <div key={i} className={styles.timelineItem}>
                <div className={styles.timelineTime}>{item.time}</div>
                <div className={styles.timelineDotWrap}>
                  <div className={styles.timelineDot} />
                  {i < agenda.length - 1 && <div className={styles.timelineLine} />}
                </div>
                <div className={styles.timelineContent}>
                  <div className={styles.timelineTitle}>{item.title}</div>
                  <div className={styles.timelineDesc}>{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Location ── */}
      <section className={styles.section}>
        <div className={styles.container}>
          <h2 className={styles.sectionTitle}>Location</h2>
          <div className={styles.locationCard}>
            <div className={styles.locationIcon}>📍</div>
            <div>
              <div className={styles.locationName}>Sendbird Seoul Office</div>
              <div className={styles.locationAddress}>서울 강남구 선릉로 514 16층</div>
              <div className={styles.locationAddress}>514 Seonneung-ro, Gangnam-gu, Seoul · 16th Floor</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Registration ── */}
      <section className={styles.section} ref={registerRef}>
        <div className={styles.container}>
          <h2 className={styles.sectionTitle}>Register</h2>
          <p className={styles.formSubtitle}>Spots are limited — secure yours today.</p>
          <div className={styles.registerCard}>
            <div className={styles.registerCardInner}>
              <p className={styles.registerCardText}>
                Fill out the short form below to reserve your spot at the 2026 Sendbird OpenHouse.
                We&apos;ll send a confirmation to your email once your registration is received.
              </p>
              <a
                href={GOOGLE_FORM_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.submitButton}
              >
                Register Now
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/sendbird-logo.png" alt="Sendbird" height={24} className={styles.logo} />
        <p className={styles.footerText}>서울 강남구 선릉로 514 16층 · Seoul, South Korea</p>
        <p className={styles.footerText}>© 2026 Sendbird Inc. All rights reserved.</p>
      </footer>
    </main>
  )
}
