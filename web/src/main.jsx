import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const EMPTY_PLAN = { title: "", target: "", saved: "0", monthly: "0" };
const EMPTY_ANSWERS = { horizon: "", reaction: "", experience: "" };
const QUESTIONS = [
  ["horizon", "When might you need the money?", ["Within 2 years", "In 2 to 5 years", "After 5 years"]],
  ["reaction", "How would a temporary loss feel?", ["Very uncomfortable", "Somewhat uncomfortable", "Manageable"]],
  ["experience", "How familiar are you with investing?", ["Just starting", "Some experience", "Very familiar"]],
];
const currency = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
});

async function api(path, method = "GET", data) {
  const response = await fetch(`/api/${path}`, {
    method,
    headers: data ? { "Content-Type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || (response.status === 429
      ? "Too many requests. Try again in a minute."
      : "The request could not be completed."));
    error.status = response.status;
    throw error;
  }
  return body;
}

function Brand() {
  return <div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>Planroom</div>;
}

function Auth({ onSignIn }) {
  const [register, setRegister] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function enter(path, data) {
    setPending(true);
    setError("");
    try {
      onSignIn(await api(path, "POST", data));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setPending(false);
    }
  }

  return <main className="auth-layout">
    <div className="auth-intro">
      <Brand />
      <div>
        <p className="kicker">Client workspace</p>
        <h1>A place to plan what’s next.</h1>
        <p>Set a savings goal, keep track of your progress and capture your preferences in one workspace.</p>
      </div>
      <button className="demo-button" disabled={pending} onClick={() => enter("auth/demo")}>Explore with sample data <span aria-hidden="true">↗</span></button>
    </div>
    <section className="auth-form" aria-labelledby="auth-title">
      <h2 id="auth-title">{register ? "Create an account" : "Sign in"}</h2>
      <form onSubmit={(event) => {
        event.preventDefault();
        enter(register ? "auth/register" : "auth/login", Object.fromEntries(new FormData(event.currentTarget)));
      }}>
        {register && <label>Name<input name="name" autoComplete="name" required maxLength={80} /></label>}
        <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
        <label>Password<input name="password" type="password" autoComplete={register ? "new-password" : "current-password"} required minLength={register ? 12 : undefined} maxLength={128} /></label>
        {register && <p className="muted">Use at least 12 characters and a sample email for this demo.</p>}
        <button className="primary" disabled={pending}>{register ? "Create account" : "Sign in"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="text-button" disabled={pending} onClick={() => { setRegister(!register); setError(""); }}>
        {register ? "Already have an account? Sign in" : "New here? Create a sample account"}
      </button>
    </section>
  </main>;
}

function Dashboard({ workspace, onChange, onSignOut }) {
  const [plan, setPlan] = useState(workspace.plan || EMPTY_PLAN);
  const [answers, setAnswers] = useState(workspace.questionnaire || EMPTY_ANSWERS);
  const [feedback, setFeedback] = useState({});
  const [busy, setBusy] = useState("");
  const savedPlan = workspace.plan;
  const progress = savedPlan ? Math.min(100, Math.floor(savedPlan.saved / savedPlan.target * 100)) : 0;
  const remaining = savedPlan ? Math.max(0, savedPlan.target - savedPlan.saved) : 0;
  const months = savedPlan?.monthly ? Math.ceil(remaining / savedPlan.monthly) : null;

  async function submit(section, action) {
    setBusy(section);
    setFeedback({ section });
    try {
      await action();
      setFeedback({ section, message: "Saved." });
    } catch (error) {
      if (error.status === 401) {
        onSignOut();
        return;
      }
      setFeedback({ section, message: error.message, error: true });
    } finally {
      setBusy("");
    }
  }

  function status(section) {
    return feedback.section === section && feedback.message && <span className={feedback.error ? "error" : "saved"} role={feedback.error ? "alert" : "status"}>{feedback.message}</span>;
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Workspace">
        <a href="#overview">Overview</a>
        <a href="#savings">Savings plan</a>
        <a href="#questionnaire">Questionnaire</a>
      </nav>
      <div className="sidebar-footer">
        <a href="/api/docs" target="_blank" rel="noreferrer">API reference ↗</a>
        <span>Portfolio demo</span>
      </div>
    </aside>
    <main className="dashboard" id="overview">
      <header className="topbar">
        <span>Client workspace</span>
        <div className="account">
          <span className="avatar" aria-hidden="true">{workspace.name.slice(0, 1).toUpperCase()}</span>
          <span>{workspace.name}</span>
          <button className="text-button" disabled={!!busy} onClick={() => submit("account", async () => {
            await api("auth/logout", "POST");
            onSignOut();
          })}>Sign out</button>
        </div>
      </header>
      {status("account")}
      <div className="content">
        <section className="summary" aria-labelledby="overview-title">
          <header>
            <p className="kicker">Planning overview</p>
            <h1 id="overview-title">Your financial plan</h1>
            <p>Track a savings goal and keep your planning preferences up to date.</p>
          </header>
          {savedPlan ? <div className="goal">
            <div className="goal-heading">
              <div><p className="kicker">Savings goal</p><h2>{savedPlan.title}</h2></div>
              <div className="goal-amount"><strong>{currency.format(savedPlan.saved)}</strong><small>of {currency.format(savedPlan.target)} saved</small></div>
            </div>
            <progress aria-label="Savings goal progress" value={progress} max="100">{progress}%</progress>
            <div className="progress-caption"><span>{progress}% funded</span><span>{currency.format(remaining)} remaining</span></div>
          </div> : <div className="goal"><h2>Start with a savings goal</h2><p>Enter an amount and a monthly contribution below to see your timeline.</p></div>}
        </section>
        <div className="metrics">
          <div><span>Monthly contribution</span><strong>{savedPlan ? currency.format(savedPlan.monthly) : "—"}</strong></div>
          <div><span>Estimated time to goal</span><strong>{savedPlan && !remaining ? "Goal reached" : months === null ? "—" : `${months} ${months === 1 ? "month" : "months"}`}</strong></div>
          <div><span>Planning questionnaire</span><strong>{workspace.questionnaire ? "Complete" : "Pending"}</strong></div>
        </div>
        <div className="panels">
          <section className="panel" id="savings" aria-labelledby="savings-title">
            <h2 id="savings-title">Savings plan</h2>
            <p className="muted">The timeline assumes a fixed monthly contribution and zero investment growth.</p>
            <form onSubmit={(event) => {
              event.preventDefault();
              submit("plan", async () => {
                const updated = await api("plan", "PUT", { ...plan, target: Number(plan.target), saved: Number(plan.saved), monthly: Number(plan.monthly) });
                setPlan(updated);
                onChange({ ...workspace, plan: updated });
              });
            }}>
              <label>Goal name<input value={plan.title} maxLength={80} required onChange={(event) => setPlan({ ...plan, title: event.target.value })} /></label>
              <div className="form-grid">
                {[["target", "Target (USD)"], ["saved", "Saved (USD)"], ["monthly", "Monthly (USD)"]].map(([key, label]) =>
                  <label key={key}>{label}<input type="number" min={key === "target" ? 1 : 0} max={10_000_000} step="1" required value={plan[key]} onChange={(event) => setPlan({ ...plan, [key]: event.target.value })} /></label>)}
              </div>
              <div className="form-actions"><button className="primary" disabled={!!busy}>Save plan</button>{status("plan")}</div>
            </form>
          </section>
          <section className="panel" id="questionnaire" aria-labelledby="question-title">
            <h2 id="question-title">Planning questionnaire</h2>
            <p className="muted">Record your preferences for a future conversation with an adviser.</p>
            <form onSubmit={(event) => {
              event.preventDefault();
              submit("questionnaire", async () => {
                const updated = await api("questionnaire", "PUT", answers);
                onChange({ ...workspace, questionnaire: updated });
              });
            }}>
              {QUESTIONS.map(([key, question, options]) => <label key={key}>{question}
                <select required value={answers[key]} onChange={(event) => setAnswers({ ...answers, [key]: Number(event.target.value) })}>
                  <option value="" disabled>Select an answer</option>
                  {options.map((option, index) => <option key={option} value={index + 1}>{option}</option>)}
                </select>
              </label>)}
              <div className="form-actions"><button className="primary" disabled={!!busy}>Save answers</button>{status("questionnaire")}</div>
            </form>
          </section>
        </div>
        <footer>Planroom is a portfolio demo. Use fictional information.</footer>
      </div>
    </main>
  </div>;
}

function App() {
  const [workspace, setWorkspace] = useState(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    api("workspace").then(setWorkspace).catch((failure) => {
      if (failure.status === 401) setWorkspace(null);
      else setError("The workspace is unavailable. Reload the page to try again.");
    });
  }, []);

  if (error) return <main className="loading" role="alert">{error}</main>;
  if (workspace === undefined) return <main className="loading" role="status">Loading workspace…</main>;
  if (workspace === null) return <Auth onSignIn={setWorkspace} />;
  return <Dashboard workspace={workspace} onChange={setWorkspace} onSignOut={() => setWorkspace(null)} />;
}

createRoot(document.getElementById("root")).render(<App />);
