import { LanguageMode, shellCopy } from '../i18n';

interface LanguageSettingsButtonProps {
  language: LanguageMode;
  onLanguageChange: (language: LanguageMode) => void;
}

export const LanguageSettingsButton = ({
  language,
  onLanguageChange
}: LanguageSettingsButtonProps) => {
  const copy = shellCopy[language].languageMenu;
  const nextLanguage: LanguageMode = language === 'zh' ? 'en' : 'zh';
  const buttonLabel = nextLanguage === 'zh' ? copy.zhLabel : copy.enLabel;
  const buttonIcon = nextLanguage === 'zh' ? '中' : 'E';

  return (
    <button
      type="button"
      onClick={() => onLanguageChange(nextLanguage)}
      className="theme-top-button h-12 w-12 justify-center rounded-2xl px-0 py-0"
      aria-label={buttonLabel}
      title={buttonLabel}
    >
      <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-semibold tracking-[0.08em]">
        {buttonIcon}
      </span>
    </button>
  );
};
