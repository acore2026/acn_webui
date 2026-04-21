import { NavKey } from '../types';
import { LanguageMode, shellCopy } from '../i18n';
import { AgentsIcon, ControlIcon, NetworkIcon, OverviewIcon, SettingsIcon, SignalIcon } from './icons';
import { LanguageSettingsButton } from './LanguageSettingsButton';
import { ThemeMode, ThemeSettingsButton } from './ThemeSettingsButton';

interface SidebarNavProps {
  activeTab: NavKey;
  language: LanguageMode;
  theme: ThemeMode;
  fullDemoBusy: boolean;
  fullDemoMessage: string | null;
  onLanguageChange: (language: LanguageMode) => void;
  onRunFullDemo: () => Promise<void>;
  onSelect: (tab: NavKey) => void;
  onThemeChange: (theme: ThemeMode) => void;
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

export const SidebarNav = ({
  activeTab,
  language,
  theme,
  fullDemoBusy,
  fullDemoMessage,
  onLanguageChange,
  onRunFullDemo,
  onSelect,
  onThemeChange
}: SidebarNavProps) => {
  const copy = shellCopy[language];
  return (
    <aside className="theme-sidebar relative z-20 border-b backdrop-blur-xl md:fixed md:inset-y-0 md:left-0 md:w-72 md:border-b-0 md:border-r">
      <div className="flex h-full flex-col px-4 py-5 md:px-6 md:py-8">
        <div className="mb-6 flex items-center gap-3 md:mb-10">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 via-blue-500 to-emerald-400 text-slate-950 shadow-glow">
            <OverviewIcon className="h-6 w-6" />
          </div>
          <div>
            <p className="theme-sidebar-brand text-xs font-semibold uppercase tracking-[0.28em]">
              {copy.brandEyebrow}
            </p>
            <h1 className="theme-title text-xl font-semibold">{copy.brandTitle}</h1>
          </div>
        </div>

        <nav className="flex flex-row gap-2 overflow-x-auto pb-2 md:flex-col md:overflow-visible">
          {navItems.map(({ key, label, Icon }) => {
            const isActive = key === activeTab;
            const navCopy = copy.nav[key];

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
                  <span className="text-sm font-medium">{navCopy.label}</span>
                  <span className="theme-muted text-xs">{navCopy.detail}</span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto hidden pt-6 md:block">
          <button
            type="button"
            onClick={() => {
              void onRunFullDemo();
            }}
            disabled={fullDemoBusy}
            className={[
              'theme-top-button w-full justify-start px-4 py-3',
              fullDemoBusy ? 'cursor-wait opacity-70' : ''
            ].join(' ')}
          >
            <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
              <SignalIcon />
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="text-sm font-medium">{copy.demoAction.label}</span>
              <span className="theme-muted text-xs">
                {fullDemoBusy ? copy.demoAction.running : copy.demoAction.detail}
              </span>
            </span>
          </button>

          <p className="theme-soft mt-3 min-h-[2.5rem] px-1 text-xs leading-5">
            {fullDemoMessage || copy.demoAction.ready}
          </p>

          <div className="pt-3 md:flex md:items-center md:gap-3">
            <ThemeSettingsButton theme={theme} language={language} onThemeChange={onThemeChange} />
            <LanguageSettingsButton language={language} onLanguageChange={onLanguageChange} />
          </div>
        </div>
      </div>
    </aside>
  );
};
