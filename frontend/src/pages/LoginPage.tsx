import { Activity, CheckCircle2, GitBranch, Layers, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../api';
import { setToken } from '../lib/auth';

const FEATURES = [
  { icon: Layers, text: 'Atomic job claiming with FOR UPDATE SKIP LOCKED' },
  { icon: GitBranch, text: 'Retries, exponential backoff & dead-letter queue' },
  { icon: ShieldCheck, text: 'Heartbeats + reaper for crash recovery' },
  { icon: CheckCircle2, text: 'Delayed & cron scheduling built in' },
];

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgName, setOrgName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = mode === 'register'
        ? await register(email, password, orgName)
        : await login(email, password);
      setToken(res.access_token);
      navigate('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        .response?.data?.message ?? 'Authentication failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      {/* Brand panel */}
      <div className="auth__brand">
        <div className="auth__brand-inner">
          <div className="auth__logo">
            <div className="auth__logo-mark"><Activity size={20} strokeWidth={2.5} /></div>
            <span className="auth__logo-text">Scheduler</span>
          </div>
          <h1 className="auth__headline">
            Distributed job execution,<br />built for reliability.
          </h1>
          <p className="auth__lede">
            Submit background jobs and let a fleet of workers atomically claim and run
            them — with full observability from a single control plane.
          </p>
          <ul className="auth__features">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="auth__feature">
                <span className="auth__feature-icon"><Icon size={15} /></span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="auth__brand-glow" />
      </div>

      {/* Form panel */}
      <div className="auth__form-panel">
        <div className="auth-card">
          <div className="auth-card__head">
            <h2 className="auth-card__title">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="auth-card__sub">
              {mode === 'login'
                ? 'Sign in to your control plane'
                : 'Set up an organisation to get started'}
            </p>
          </div>

          <div className="auth-tabs">
            <button
              className={`auth-tab ${mode === 'login' ? 'auth-tab--active' : ''}`}
              onClick={() => setMode('login')}
            >Sign in</button>
            <button
              className={`auth-tab ${mode === 'register' ? 'auth-tab--active' : ''}`}
              onClick={() => setMode('register')}
            >Register</button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <label className="field">
                <span className="field__label">Organisation</span>
                <input className="field__input" type="text" value={orgName}
                  onChange={(e) => setOrgName(e.target.value)} placeholder="Acme Corp" required />
              </label>
            )}
            <label className="field">
              <span className="field__label">Email</span>
              <input className="field__input" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
            </label>
            <label className="field">
              <span className="field__label">Password</span>
              <input className="field__input" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
            </label>

            {error && <div className="alert alert--error">{error}</div>}

            <button type="submit" className="btn btn--primary btn--lg auth-submit" disabled={loading}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="auth-card__foot">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button className="auth-link" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
              {mode === 'login' ? 'Register' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
