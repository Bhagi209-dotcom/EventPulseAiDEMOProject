import React, { useEffect, useState, useRef } from 'react'
import {
  Activity,
  BarChart3,
  Cpu,
  MessageSquare,
  Smartphone,
  Monitor,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Send,
  PlusCircle,
  QrCode,
  Copy,
  X,
} from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'

const TIER_STYLES = {
  Optimal: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  'Mild Drift': 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  'Moderate Slump': 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'Severe Disengagement': 'bg-rose-500/20 text-rose-300 border-rose-500/40',
}

export default function App() {
  const [isAttendeeOnly] = useState(
    () => new URLSearchParams(window.location.search).get('view') === 'attendee'
  )
  const [view, setView] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('view') === 'attendee' ? 'attendee' : 'presenter'
  }) // presenter | attendee | benchmarks
  const [sessionCode] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('session') || 'DEMO-101'
  })
  const [lanIp, setLanIp] = useState('127.0.0.1')
  const [showQrModal, setShowQrModal] = useState(false)
  const [qrUrlOverride, setQrUrlOverride] = useState('')
  const [voterToken] = useState(() => {
    let tok = localStorage.getItem('ep_voter_token')
    if (!tok) {
      tok = (crypto.randomUUID ? crypto.randomUUID() : `ep-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`)
      localStorage.setItem('ep_voter_token', tok)
    }
    return tok
  })
  const [votedPolls, setVotedPolls] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('ep_voted_polls') || '{}')
    } catch {
      return {}
    }
  })
  const [telemetry, setTelemetry] = useState(null)
  const [history, setHistory] = useState([])
  const [benchmarks, setBenchmarks] = useState([])
  const [datasetSize, setDatasetSize] = useState(0)
  const [wsConnected, setWsConnected] = useState(false)

  // Poll creator state
  const [pollQ, setPollQ] = useState('')
  const [pollOpts, setPollOpts] = useState(['Yes, crystal clear', 'Need another example', 'Too fast'])

  // Attendee Q&A state
  const [qaText, setQaText] = useState('')
  const [lastQaResult, setLastQaResult] = useState(null)
  const [showRefGuide, setShowRefGuide] = useState(false)
  const [toast, setToast] = useState('')
  const wsRef = useRef(null)

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 2500)
  }

  const applySnapshot = (data) => {
    setTelemetry(data)
    setHistory((prev) => {
      const next = [
        ...prev,
        {
          t: new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
          risk: data.prediction?.risk_percent ?? 0,
          sentiment: ((data.metrics?.sentiment_score ?? 0) + 1) * 50,
        },
      ]
      return next.slice(-24)
    })
  }

  useEffect(() => {
    fetch(`/api/v1/sessions/active?code=${sessionCode}`)
      .then((r) => r.json())
      .then(applySnapshot)
      .catch(() => {})

    fetch('/api/v1/analytics/benchmarks')
      .then((r) => r.json())
      .then((d) => {
        setBenchmarks(d.benchmarks || [])
        setDatasetSize(d.dataset_size || 0)
      })
      .catch(() => {})

    fetch('/api/v1/network/info')
      .then((r) => r.json())
      .then((d) => {
        if (d?.lan_ip) setLanIp(d.lan_ip)
      })
      .catch(() => {})

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/session/${sessionCode}`)
    wsRef.current = ws
    ws.onopen = () => setWsConnected(true)
    ws.onclose = () => setWsConnected(false)
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'telemetry_update' && msg.data) {
          applySnapshot(msg.data)
        }
      } catch {}
    }
    return () => ws.close()
  }, [sessionCode])

  const simulate = async (mode) => {
    const r = await fetch('/api/v1/demo/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_code: sessionCode, mode }),
    })
    if (r.ok) {
      applySnapshot(await r.json())
      showToast(`Simulated: ${mode.replace('_', ' ')}`)
    }
  }

  const sendReaction = async (reaction) => {
    const r = await fetch('/api/v1/events/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_code: sessionCode, reaction }),
    })
    if (r.ok) {
      applySnapshot(await r.json())
      showToast(`Sent ${reaction} pulse`)
    }
  }

  const createPoll = async (e) => {
    e.preventDefault()
    if (!pollQ.trim()) return
    const options = pollOpts.map((s) => s.trim()).filter(Boolean)
    if (options.length < 2) return
    const r = await fetch('/api/v1/polls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_code: sessionCode, question: pollQ, options }),
    })
    if (r.ok) {
      applySnapshot(await r.json())
      setPollQ('')
      showToast('Live poll launched')
    }
  }

  const votePoll = async (pollId, optionIndex) => {
    const r = await fetch(`/api/v1/polls/${pollId}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ option_index: optionIndex, voter_token: voterToken }),
    })
    if (r.ok) {
      const nextVoted = { ...votedPolls, [pollId]: optionIndex }
      setVotedPolls(nextVoted)
      localStorage.setItem('ep_voted_polls', JSON.stringify(nextVoted))
      applySnapshot(await r.json())
      showToast('Vote recorded')
    } else if (r.status === 409) {
      showToast('Already voted in this poll')
    }
  }

  const submitQA = async (e) => {
    e.preventDefault()
    if (!qaText.trim()) return
    const r = await fetch('/api/v1/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_code: sessionCode, text: qaText }),
    })
    if (r.ok) {
      const snap = await r.json()
      applySnapshot(snap)
      setLastQaResult(snap.qa?.[0] || null)
      setQaText('')
      showToast('Anonymous question sent (DPDP sanitized)')
    }
  }

  const pred = telemetry?.prediction
  const metrics = telemetry?.metrics
  const tierClass = TIER_STYLES[pred?.risk_tier] || TIER_STYLES.Optimal

  const buildSvgPath = (key) => {
    if (history.length < 2) return ''
    const w = 520
    const h = 120
    return history
      .map((pt, i) => {
        const x = (i / (history.length - 1)) * w
        const y = h - (Math.min(100, Math.max(0, pt[key])) / 100) * (h - 16) - 8
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-500/20 border border-indigo-400/40 flex items-center justify-center">
              <Activity className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h1 className="font-semibold text-base tracking-tight">EventPulse AI</h1>
              <p className="text-xs text-slate-400">
                Session <span className="text-indigo-300 font-mono">{sessionCode}</span> •{' '}
                <span className={wsConnected ? 'text-emerald-400' : 'text-amber-400'}>
                  {wsConnected ? 'WS Live' : 'Polling'}
                </span>
              </p>
            </div>
          </div>

          {isAttendeeOnly ? (
            <span className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border bg-indigo-600/20 border-indigo-500/40 text-indigo-300">
              <Smartphone className="w-3.5 h-3.5" /> Attendee Mode
            </span>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setView('presenter')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border ${
                  view === 'presenter'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Monitor className="w-3.5 h-3.5" /> Presenter HUD
              </button>
              <button
                onClick={() => setView('attendee')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border ${
                  view === 'attendee'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Smartphone className="w-3.5 h-3.5" /> Attendee Mobile
              </button>
              <button
                onClick={() => setView('benchmarks')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border ${
                  view === 'benchmarks'
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Model Benchmarks
              </button>
              <button
                onClick={() => setShowQrModal(true)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 border bg-slate-900 border-slate-700 text-emerald-300 hover:bg-slate-800"
              >
                <QrCode className="w-3.5 h-3.5" /> Mobile QR
              </button>
            </div>
          )}
        </div>
      </header>

      {showQrModal && (() => {
        const defaultQrUrl = `http://${lanIp}:${window.location.port || 5173}/?view=attendee&session=${sessionCode}`
        const activeQrUrl = qrUrlOverride || defaultQrUrl
        return (
          <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <QrCode className="w-4 h-4 text-emerald-400" /> Attendee Mobile QR
                </h3>
                <button
                  onClick={() => setShowQrModal(false)}
                  className="text-slate-400 hover:text-white p-1 rounded-lg"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="bg-white p-4 rounded-xl flex items-center justify-center">
                <QRCodeSVG value={activeQrUrl} size={196} level="M" />
              </div>
              <p className="text-[11px] text-emerald-300 text-center">
                Generated 100% offline in-browser with zero external APIs.
              </p>
              <div className="space-y-2">
                <label className="block text-[11px] text-slate-400">
                  Mobile Join URL (editable LAN IP / port)
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={activeQrUrl}
                    onChange={(e) => setQrUrlOverride(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                  />
                  <button
                    onClick={() => {
                      navigator.clipboard?.writeText(activeQrUrl)
                      showToast('Join link copied')
                    }}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium flex items-center gap-1"
                  >
                    <Copy className="w-3.5 h-3.5" /> Copy
                  </button>
                </div>
              </div>
            </div>
          </div>
        )
      })()}

      {toast && (
        <div className="fixed bottom-5 right-5 z-50 bg-indigo-600 text-white text-xs font-medium px-4 py-2.5 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6">
        {view === 'presenter' && (
          <div className="space-y-6">
            <div className="bg-indigo-500/10 border border-indigo-500/25 rounded-xl px-4 py-2.5 text-xs text-indigo-200">
              <span className="font-semibold text-indigo-300">What This Page Does:</span> Real-time presenter cockpit — monitor audience disengagement risk, SHAP feature drivers, live polls, and DPDP-sanitized Q&amp;A.
            </div>
            {/* Simulator Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/70 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Zap className="w-4 h-4 text-amber-400" />
                <span className="font-medium">Simulate Audience Pulse:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => simulate('engaged')}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25"
                >
                  Normal Flow
                </button>
                <button
                  onClick={() => simulate('confusion_spike')}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25"
                >
                  Confusion Spike
                </button>
                <button
                  onClick={() => simulate('disengagement_drift')}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-500/25"
                >
                  Drop-off Drift
                </button>
              </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <p className="text-xs text-slate-400">Disengagement Risk</p>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-bold">{pred ? `${pred.risk_percent}%` : '--'}</span>
                  <span className={`text-xs px-2.5 py-0.5 rounded-full border ${tierClass}`}>
                    {pred?.risk_tier || 'Loading'}
                  </span>
                </div>
                {pred?.recommended_action && (
                  <p className="mt-2 text-[11px] text-slate-300 leading-snug">{pred.recommended_action}</p>
                )}
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <p className="text-xs text-slate-400">Reaction Velocity</p>
                <p className="mt-2 text-2xl font-bold">{metrics ? `${metrics.reactions_per_min}/min` : '--'}</p>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <p className="text-xs text-slate-400">Avg Dwell Time</p>
                <p className="mt-2 text-2xl font-bold">{metrics ? `${metrics.avg_dwell_seconds}s` : '--'}</p>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                <p className="text-xs text-slate-400">SHAP Inference Latency</p>
                <p className="mt-2 text-2xl font-bold text-indigo-300">
                  {pred ? `${pred.inference_latency_ms} ms` : '--'}
                </p>
              </div>
            </div>

            {/* Timeline + SHAP */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold">Live Sentiment & Risk Timeline</h2>
                  <div className="flex gap-4 text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-400" /> Risk %
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Sentiment
                    </span>
                  </div>
                </div>
                <svg viewBox="0 0 520 120" className="w-full h-40 bg-slate-950/60 rounded-lg border border-slate-800/80">
                  <line x1="0" y1="30" x2="520" y2="30" stroke="#1e293b" strokeDasharray="4 4" />
                  <line x1="0" y1="60" x2="520" y2="60" stroke="#1e293b" strokeDasharray="4 4" />
                  <line x1="0" y1="90" x2="520" y2="90" stroke="#1e293b" strokeDasharray="4 4" />
                  {history.length >= 2 && (
                    <>
                      <path d={buildSvgPath('sentiment')} fill="none" stroke="#34d399" strokeWidth="2.2" />
                      <path d={buildSvgPath('risk')} fill="none" stroke="#fb7185" strokeWidth="2.2" />
                    </>
                  )}
                </svg>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Cpu className="w-4 h-4 text-indigo-400" />
                  <h2 className="text-sm font-semibold">Explainable SHAP Attribution</h2>
                </div>
                <div className="space-y-2.5">
                  {(pred?.top_shap_attributions || []).map((item) => {
                    const isRisk = item.shap_value >= 0
                    const width = Math.min(100, Math.abs(item.shap_value) * 120)
                    return (
                      <div key={item.feature} className="text-xs">
                        <div className="flex justify-between text-slate-300 mb-1">
                          <span className="font-mono">{item.feature}</span>
                          <span className={isRisk ? 'text-rose-400' : 'text-emerald-400'}>
                            {isRisk ? '+' : ''}
                            {item.shap_value}
                          </span>
                        </div>
                        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${isRisk ? 'bg-rose-500' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.max(6, width)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Poll Creator + Anonymous Q&A Feed */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <PlusCircle className="w-4 h-4 text-indigo-400" /> Launch Live Poll
                </h2>
                <form onSubmit={createPoll} className="space-y-3">
                  <input
                    value={pollQ}
                    onChange={(e) => setPollQ(e.target.value)}
                    placeholder="Ask the audience a quick check-in..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
                  />
                  <div className="space-y-2">
                    {pollOpts.map((opt, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          value={opt}
                          onChange={(e) =>
                            setPollOpts((prev) => prev.map((v, i) => (i === idx ? e.target.value : v)))
                          }
                          placeholder={`Option ${idx + 1}`}
                          className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                        />
                        {pollOpts.length > 2 && (
                          <button
                            type="button"
                            onClick={() => setPollOpts((prev) => prev.filter((_, i) => i !== idx))}
                            className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 text-xs"
                            title="Remove option"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                    {pollOpts.length < 6 && (
                      <button
                        type="button"
                        onClick={() => setPollOpts((prev) => [...prev, ''])}
                        className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                      >
                        + Add Option
                      </button>
                    )}
                  </div>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium"
                  >
                    Publish Poll
                  </button>
                </form>
                <div className="mt-4 space-y-3">
                  {(telemetry?.polls || []).slice(0, 2).map((p) => (
                    <div key={p.id} className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                      <p className="text-xs font-medium mb-2">{p.question}</p>
                      <div className="space-y-1.5">
                        {p.options.map((opt, idx) => (
                          <div key={idx} className="flex justify-between text-xs text-slate-400">
                            <span>{opt}</span>
                            <span className="font-mono text-indigo-300">{p.counts[idx]} votes</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h2 className="text-sm font-semibold mb-1 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-indigo-400" /> Anonymous Q&A Feed (DPDP Sanitized)
                </h2>
                <p className="text-[11px] text-slate-400 mb-3">
                  VADER + Intent NLP classifies each question (Positive Praise / Question &amp; Clarification / Improvement Suggestion / Technical Feedback / Support Request) and masks PII ([REDACTED]).
                </p>
                <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                  {(telemetry?.qa || []).length === 0 ? (
                    <p className="text-xs text-slate-500">No questions yet. Simulate or submit from Attendee view.</p>
                  ) : (
                    telemetry.qa.map((q) => (
                      <div key={q.id} className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                            {q.feedback_type || 'General Feedback'}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                              q.sentiment_label === 'Positive'
                                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                : q.sentiment_label === 'Negative'
                                  ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                                  : 'bg-slate-800 text-slate-300 border-slate-700'
                            }`}
                          >
                            {q.sentiment_label || 'Neutral'}
                          </span>
                        </div>
                        <p className="text-slate-200">{q.text}</p>
                        <p className="mt-1 text-[11px] text-slate-500">{q.nlp_explanation || `VADER compound: ${q.vader_compound}`}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Collapsible Reference Guide */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <button
                type="button"
                onClick={() => setShowRefGuide((v) => !v)}
                className="w-full flex items-center justify-between text-xs font-semibold text-slate-200"
              >
                <span>Reference Guide: Metrics &amp; SHAP Features</span>
                <span className="text-indigo-400">{showRefGuide ? 'Hide' : 'Show'}</span>
              </button>
              {showRefGuide && (
                <div className="mt-3 pt-3 border-t border-slate-800 grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] text-slate-400">
                  <div>
                    <p className="font-semibold text-slate-300 mb-1">Core Telemetry Metrics</p>
                    <p>• Disengagement Risk: Calibrated CatBoost probability across 4 risk tiers.</p>
                    <p>• Reaction Velocity: Audience pulse taps per minute (3m rolling window).</p>
                    <p>• Avg Dwell Time: Mean active attention duration in seconds.</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-300 mb-1">SHAP Feature Drivers</p>
                    <p>• Red (+) bars push disengagement risk higher; Green (−) bars reduce risk.</p>
                    <p>• Top drivers include dwell time, confusion ratio, VADER sentiment, and Q&amp;A velocity.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {view === 'attendee' && (
          <div className="max-w-md mx-auto space-y-5">
            <div className="bg-indigo-500/10 border border-indigo-500/25 rounded-xl px-4 py-2.5 text-xs text-indigo-200">
              <span className="font-semibold text-indigo-300">What This Page Does:</span> Mobile-first attendee view — send 1-tap pulse reactions, vote in live polls, and ask anonymous DPDP-sanitized questions.
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-center">
              <h2 className="text-base font-semibold">1-Tap Audience Pulse</h2>
              <p className="text-xs text-slate-400 mt-1">Zero-login • Instant anonymous feedback</p>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <button
                  onClick={() => sendReaction('positive')}
                  className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 hover:bg-emerald-500/25 text-emerald-300 text-sm font-medium"
                >
                  Positive
                </button>
                <button
                  onClick={() => sendReaction('neutral')}
                  className="p-4 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-200 text-sm font-medium"
                >
                  Neutral
                </button>
                <button
                  onClick={() => sendReaction('confused')}
                  className="p-4 rounded-xl bg-amber-500/15 border border-amber-500/30 hover:bg-amber-500/25 text-amber-300 text-sm font-medium"
                >
                  Confused
                </button>
                <button
                  onClick={() => sendReaction('disengaged')}
                  className="p-4 rounded-xl bg-rose-500/15 border border-rose-500/30 hover:bg-rose-500/25 text-rose-300 text-sm font-medium"
                >
                  Disengaged
                </button>
              </div>
            </div>

            {(telemetry?.polls || []).length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <h3 className="text-sm font-semibold mb-3">Live Poll</h3>
                {telemetry.polls.slice(0, 1).map((p) => {
                  const chosenIdx = votedPolls[p.id]
                  const hasVoted = chosenIdx !== undefined
                  return (
                    <div key={p.id} className="space-y-2">
                      <p className="text-xs text-slate-300 mb-2">{p.question}</p>
                      {p.options.map((opt, idx) => {
                        const isChosen = chosenIdx === idx
                        return (
                          <button
                            key={idx}
                            disabled={hasVoted}
                            onClick={() => votePoll(p.id, idx)}
                            className={`w-full text-left px-3 py-2 rounded-lg border text-xs flex justify-between items-center ${
                              isChosen
                                ? 'bg-indigo-600/20 border-indigo-500 text-indigo-200'
                                : hasVoted
                                ? 'bg-slate-950/60 border-slate-800 text-slate-500 cursor-not-allowed'
                                : 'bg-slate-950 border-slate-800 hover:border-indigo-500'
                            }`}
                          >
                            <span>
                              {opt}
                              {isChosen && (
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/30 text-indigo-200">
                                  Voted
                                </span>
                              )}
                            </span>
                            <span className="text-indigo-400">{p.counts[idx]}</span>
                          </button>
                        )
                      })}
                    </div>
                  )
                })}
              </div>
            )}

            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <h3 className="text-sm font-semibold mb-1">Ask Anonymously</h3>
              <p className="text-[11px] text-slate-400 mb-2.5">
                VADER + Intent NLP classifies each question (Positive Praise / Question &amp; Clarification / Improvement Suggestion / Technical Feedback / Support Request) and masks PII ([REDACTED]).
              </p>
              <form onSubmit={submitQA} className="space-y-2.5">
                <textarea
                  rows={3}
                  value={qaText}
                  onChange={(e) => setQaText(e.target.value)}
                  placeholder="Type your question (emails/phones are auto-redacted)..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs focus:outline-none focus:border-indigo-500"
                />
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium flex items-center justify-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" /> Submit Question
                </button>
              </form>
              {lastQaResult && (
                <div className="mt-3 p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px]">
                  <div className="flex flex-wrap items-center gap-1.5 mb-1">
                    <span className="px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 font-medium">
                      {lastQaResult.feedback_type}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-medium">
                      {lastQaResult.sentiment_label}
                    </span>
                  </div>
                  <p className="text-slate-400">{lastQaResult.nlp_explanation}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {view === 'benchmarks' && (
          <div className="space-y-4">
            <div className="bg-indigo-500/10 border border-indigo-500/25 rounded-xl px-4 py-2.5 text-xs text-indigo-200">
              <span className="font-semibold text-indigo-300">What This Page Does:</span> Offline ML benchmark comparison — compare Accuracy, F1, ROC-AUC, Brier Score, and training time across candidate models.
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-semibold">ML Model Benchmarks</h2>
                <p className="text-xs text-slate-400">
                  Evaluated on {datasetSize} engineered cohort telemetry records (24 features)
                </p>
              </div>
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2.5 pr-4">Model</th>
                    <th className="py-2.5 px-4">Accuracy</th>
                    <th className="py-2.5 px-4">F1 Score</th>
                    <th className="py-2.5 px-4">ROC-AUC</th>
                    <th className="py-2.5 px-4">Brier Score</th>
                    <th className="py-2.5 pl-4">Train Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {benchmarks.map((b) => (
                    <tr key={b.model} className="hover:bg-slate-800/30">
                      <td className="py-3 pr-4 font-medium text-slate-200">{b.model}</td>
                      <td className="py-3 px-4 font-mono">{b.accuracy}</td>
                      <td className="py-3 px-4 font-mono">{b.f1}</td>
                      <td className="py-3 px-4 font-mono text-indigo-300">{b.roc_auc}</td>
                      <td className="py-3 px-4 font-mono text-emerald-300">{b.brier_score}</td>
                      <td className="py-3 pl-4 font-mono text-slate-400">{b.train_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          </div>
        )}
      </main>
    </div>
  )
}
