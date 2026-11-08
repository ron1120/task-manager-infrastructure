// Floating chat bot (the round button, bottom-right). Asks the pagewise assistant (/assistant/api/ask), which
// answers questions about this repository only from its own files and shows where each answer came from.
// Hidden when the assistant container isn't running.
import { useEffect, useRef, useState } from 'react';

const ASSISTANT = '/assistant/api';
const SUGGESTIONS = [
  'How does JWT authentication work?',
  'Which ports does the stack use?',
  'What does the Terraform create?',
];

export default function HelpChat() {
  const [available, setAvailable] = useState(false);
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    fetch(`${ASSISTANT}/health`)
      .then((res) => setAvailable(res.ok))
      .catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, open]);

  if (!available) return null;

  const ask = async (text) => {
    const clean = text.trim();
    if (!clean || busy) return;
    setQuestion('');
    setBusy(true);
    setMessages((m) => [...m, { role: 'user', text: clean }]);
    try {
      const res = await fetch(`${ASSISTANT}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: clean }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'That question could not be sent.';
        setMessages((m) => [...m, { role: 'bot', text: detail, refused: true, sources: [] }]);
      } else {
        setMessages((m) => [
          ...m,
          { role: 'bot', text: data.text, refused: data.status !== 'answered', sources: data.sources },
        ]);
      }
    } catch {
      setMessages((m) => [
        ...m,
        { role: 'bot', text: 'The assistant could not be reached. Please try again.', refused: true, sources: [] },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="help">
      {open && (
        <section className="help-panel card" aria-label="Repository assistant">
          <header className="help-head">
            <div>
              <strong>Ask about this repo</strong>
              <p className="muted help-sub">AI answers from the project&apos;s own files, with sources.</p>
            </div>
            <button type="button" className="button secondary" onClick={() => setOpen(false)}>
              Close
            </button>
          </header>
          <div className="help-log" aria-live="polite">
            {messages.length === 0 && (
              <div className="help-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="help-chip" onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`help-msg ${m.role}${m.refused ? ' refused' : ''}`}>
                <p>{m.text}</p>
                {m.sources?.length > 0 && (
                  <ul className="help-sources">
                    {m.sources.map((s) => (
                      <li key={s.n}>
                        [{s.n}]{' '}
                        <a href={s.url} target="_blank" rel="noopener noreferrer">
                          {s.title} &middot; {s.heading}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {busy && <p className="muted">Looking through the repo...</p>}
            <div ref={endRef} />
          </div>
          <form
            className="help-form"
            onSubmit={(e) => {
              e.preventDefault();
              ask(question);
            }}
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question"
              maxLength={500}
              aria-label="Question"
            />
            <button type="submit" className="button" disabled={busy}>
              Ask
            </button>
          </form>
        </section>
      )}
      <button
        type="button"
        className="help-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close the repository assistant' : 'Open the repository assistant'}
        aria-expanded={open}
      >
        {open ? (
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
            <path
              d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-8l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"
              fill="currentColor"
            />
          </svg>
        )}
      </button>
    </div>
  );
}
