// Floating help chat. Asks the pagewise assistant (/assistant/api/ask), which answers only from this
// project's docs and shows where each answer came from. Hidden when the assistant isn't running.
import { useEffect, useRef, useState } from 'react';

const ASSISTANT = '/assistant/api';

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

  const send = async (e) => {
    e.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion('');
    setBusy(true);
    setMessages((m) => [...m, { role: 'user', text }]);
    try {
      const res = await fetch(`${ASSISTANT}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text }),
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
        <section className="help-panel card" aria-label="Help assistant">
          <header className="help-head">
            <strong>Ask the docs</strong>
            <button type="button" className="button secondary" onClick={() => setOpen(false)}>
              Close
            </button>
          </header>
          <div className="help-log" aria-live="polite">
            {messages.length === 0 && (
              <p className="muted">Ask how the app works. Answers come only from the project docs, with sources.</p>
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
                          {s.heading && s.heading !== s.title ? `${s.title} > ${s.heading}` : s.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {busy && <p className="muted">Looking through the docs...</p>}
            <div ref={endRef} />
          </div>
          <form className="help-form" onSubmit={send}>
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
      <button type="button" className="button help-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide help' : 'Help'}
      </button>
    </div>
  );
}
