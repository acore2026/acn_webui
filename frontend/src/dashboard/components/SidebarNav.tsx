import { NavKey } from '../types';
import { AgentsIcon, ControlIcon, NetworkIcon, OverviewIcon, SettingsIcon } from './icons';

interface SidebarNavProps {
  activeTab: NavKey;
  onSelect: (tab: NavKey) => void;
}

const navItems: Array<{
  key: NavKey;
  label: string;
  Icon: typeof OverviewIcon;
}> = [
  { key: 'overview', label: 'Overview', Icon: OverviewIcon },
  { key: 'agents', label: 'Agents', Icon: AgentsIcon },
  { key: 'network', label: 'Network', Icon: NetworkIcon },
  { key: 'control', label: 'Control', Icon: ControlIcon },
  { key: 'settings', label: 'Settings', Icon: SettingsIcon }
];

export const SidebarNav = ({ activeTab, onSelect }: SidebarNavProps) => {
  return (
    <aside className="theme-sidebar relative z-20 border-b backdrop-blur-xl md:fixed md:inset-y-0 md:left-0 md:w-72 md:border-b-0 md:border-r">
      <div className="flex h-full flex-col px-4 py-5 md:px-6 md:py-8">
        <div className="mb-6 flex items-center gap-3 md:mb-10">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 via-blue-500 to-emerald-400 text-slate-950 shadow-glow">
            <OverviewIcon className="h-6 w-6" />
          </div>
          <div>
            <p className="theme-sidebar-brand text-xs font-semibold uppercase tracking-[0.28em]">
              Command Mesh
            </p>
            <h1 className="theme-title text-xl font-semibold">Ops Dashboard</h1>
          </div>
        </div>

        <nav className="flex flex-row gap-2 overflow-x-auto pb-2 md:flex-col md:overflow-visible">
          {navItems.map(({ key, label, Icon }) => {
            const isActive = key === activeTab;

            return (
              <button
                key={key}
                type="button"
                onClick={() => onSelect(key)}
                className={[
                  'group flex min-w-[150px] items-center gap-3 rounded-2xl border px-4 py-3 text-left transition duration-200 md:min-w-0',
                  isActive
                    ? 'theme-nav-active shadow-glow'
                    : 'theme-nav-button'
                ].join(' ')}
              >
                <span
                  className={[
                    'flex h-10 w-10 items-center justify-center rounded-xl transition',
                    isActive
                      ? 'theme-accent-icon'
                      : 'theme-icon-shell theme-soft group-hover:text-[color:var(--accent-cyan-text)]'
                  ].join(' ')}
                >
                  <Icon />
                </span>
                <span className="flex flex-col">
                  <span className="text-sm font-medium">{label}</span>
                  <span className="theme-muted text-xs">
                    {key === 'overview' && 'Mission overview'}
                    {key === 'agents' && 'Roster and health'}
                    {key === 'network' && 'Topology traffic'}
                    {key === 'control' && 'Operator actions'}
                    {key === 'settings' && 'Policy controls'}
                  </span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="theme-sidebar-note mt-6 hidden rounded-3xl border p-5 md:block">
          <p className="text-xs font-semibold uppercase tracking-[0.24em]">
            Live Snapshot
          </p>
          <div className="theme-copy mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span>Mesh integrity</span>
              <span className="theme-badge-emerald rounded-full px-2.5 py-1 text-xs font-semibold">
                98.7%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Alarm window</span>
              <span className="theme-title">03 active</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Global sync</span>
              <span className="theme-title">09:26 UTC</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
