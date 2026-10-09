import { useState } from 'react';
import { UpdateService, type ReleaseInfo } from '../services/UpdateService';

export default function UpdateView() {
  const [release, setRelease] = useState<ReleaseInfo | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel narrow">
      <h2>App-Updates</h2>
      <p className="muted">GitHub Releases von GThreeD/Geed.FamilyHub</p>
      <button
        className="secondary"
        disabled={busy}
        onClick={() =>
          void perform(async () => {
            setRelease(await UpdateService.latest());
            setReady(false);
            setMessage('');
          })
        }
      >
        Neueste Version prüfen
      </button>
      {release && (
        <div className="update-release">
          <h3>{release.tag}</h3>
          <a href={release.page} target="_blank" rel="noreferrer">
            Release auf GitHub ansehen
          </a>
          <p>Das Update wird vor der Installation anhand der SHA-256-Prüfsumme geprüft.</p>
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              void perform(async () => {
                const prepared = await UpdateService.prepare();
                setReady(prepared.ready);
                setMessage(`Version ${prepared.tag} heruntergeladen und geprüft.`);
              })
            }
          >
            Update herunterladen und prüfen
          </button>
        </div>
      )}
      {ready && (
        <div className="update-release">
          <p>
            Der Server wird beim Installieren kurz offline sein. Datenbank und Tokens bleiben
            erhalten.
          </p>
          <button
            className="primary"
            disabled={busy}
            onClick={() => {
              if (!window.confirm('Update installieren und den Server neu starten?')) return;
              void perform(async () => {
                const response = await UpdateService.install();
                setMessage(response.message);
                setReady(false);
              });
            }}
          >
            Installieren und neu starten
          </button>
        </div>
      )}
      {message && <p className="notice">{message}</p>}
      {error && <p className="alert">{error}</p>}
    </section>
  );
}
