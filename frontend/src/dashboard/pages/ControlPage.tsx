import { ControlIcon, InfoIcon, WarningIcon } from '../components/icons';
import { SectionCard } from '../components/SectionCard';

interface ControlPageProps {
  clearInProgress: boolean;
  onClearEnvironment: () => Promise<void>;
  onReloadSnapshot: () => Promise<void>;
  websocketConnected: boolean;
  apiHealthy: boolean;
  statusMessage: string | null;
  statusTone: 'success' | 'warning' | 'error' | null;
}

const statusStyles = {
  success: 'theme-badge-emerald',
  warning: 'theme-badge-amber',
  error: 'theme-badge-rose'
};

export const ControlPage = ({
  clearInProgress,
  onClearEnvironment,
  onReloadSnapshot,
  websocketConnected,
  apiHealthy,
  statusMessage,
  statusTone
}: ControlPageProps) => {
  return (
    <SectionCard
      eyebrow="Control"
      title="Operator Controls"
      description="Run backend control actions from one place. Use reset carefully because it clears the monitored environment before the dashboard refreshes."
    >
      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.9fr]">
        <div className="theme-card-muted p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="panel-eyebrow">Primary Action</p>
              <h3 className="theme-title mt-2 text-xl font-semibold">Clear Environment</h3>
              <p className="theme-copy mt-3 max-w-2xl text-sm leading-6">
                Calls the backend control route for the ARF <code>/clear</code> operation, then refreshes the agent roster and dashboard snapshot.
              </p>
            </div>
            <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
              <ControlIcon />
            </span>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                void onClearEnvironment();
              }}
              disabled={clearInProgress}
              className={[
                'theme-top-button px-5 py-3',
                clearInProgress ? 'cursor-wait opacity-70' : ''
              ].join(' ')}
            >
              {clearInProgress ? 'Clearing environment...' : 'Run Clear'}
            </button>

            <button
              type="button"
              onClick={() => {
                void onReloadSnapshot();
              }}
              className="theme-top-button px-5 py-3"
            >
              Reload Snapshot
            </button>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="theme-subtle-card p-4">
              <p className="theme-muted text-xs uppercase tracking-[0.18em]">Backend Route</p>
              <p className="theme-title mt-2 text-sm font-medium">POST /api/control/clear</p>
            </div>
            <div className="theme-subtle-card p-4">
              <p className="theme-muted text-xs uppercase tracking-[0.18em]">Effect</p>
              <p className="theme-copy mt-2 text-sm leading-6">
                Resets the environment and broadcasts a fresh dashboard snapshot to all connected clients.
              </p>
            </div>
          </div>

          {statusMessage ? (
            <div className={`mt-5 rounded-3xl border px-4 py-4 text-sm leading-6 ${statusTone ? statusStyles[statusTone] : 'theme-chip'}`}>
              {statusMessage}
            </div>
          ) : null}
        </div>

        <div className="grid gap-4">
          <div className="theme-card-muted p-5">
            <div className="flex items-center gap-3">
              <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
                <InfoIcon />
              </span>
              <div>
                <h3 className="theme-title text-lg font-semibold">Control Surface Status</h3>
                <p className="theme-soft text-sm">Current connection state for control actions.</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div className="theme-subtle-card flex items-center justify-between px-4 py-3">
                <span className="theme-copy text-sm">API route</span>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${apiHealthy ? 'theme-badge-emerald' : 'theme-badge-rose'}`}>
                  {apiHealthy ? 'reachable' : 'error'}
                </span>
              </div>
              <div className="theme-subtle-card flex items-center justify-between px-4 py-3">
                <span className="theme-copy text-sm">WebSocket broadcast</span>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${websocketConnected ? 'theme-badge-emerald' : 'theme-badge-amber'}`}>
                  {websocketConnected ? 'live' : 'reconnecting'}
                </span>
              </div>
            </div>
          </div>

          <div className="theme-card-muted p-5">
            <div className="flex items-center gap-3">
              <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
                <WarningIcon />
              </span>
              <div>
                <h3 className="theme-title text-lg font-semibold">Operator Note</h3>
                <p className="theme-soft text-sm">Use clear only when you intend to reset the active environment.</p>
              </div>
            </div>

            <ul className="theme-copy mt-4 space-y-3 text-sm leading-6">
              <li className="theme-subtle-card px-4 py-3">
                The clear action is server-side and applies to the shared backend state.
              </li>
              <li className="theme-subtle-card px-4 py-3">
                A successful run refreshes agents and pushes the updated dashboard to all open WebUI sessions.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </SectionCard>
  );
};
