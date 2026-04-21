import { MoonIcon, SunIcon } from './icons';
import { LanguageMode, shellCopy } from '../i18n';

export type ThemeMode = 'dark' | 'light';

interface ThemeSettingsButtonProps {
  theme: ThemeMode;
  language: LanguageMode;
  onThemeChange: (theme: ThemeMode) => void;
}

export const ThemeSettingsButton = ({
  theme,
  language,
  onThemeChange
}: ThemeSettingsButtonProps) => {
  const copy = shellCopy[language].themeMenu;
  const nextTheme: ThemeMode = theme === 'dark' ? 'light' : 'dark';
  const buttonLabel = nextTheme === 'dark' ? copy.darkLabel : copy.lightLabel;
  const Icon = nextTheme === 'dark' ? MoonIcon : SunIcon;

  return (
    <button
      type="button"
      onClick={() => onThemeChange(nextTheme)}
      className="theme-top-button h-12 w-12 justify-center rounded-2xl px-0 py-0"
      aria-label={buttonLabel}
      title={buttonLabel}
    >
      <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
        <Icon />
      </span>
    </button>
  );
};
