import { MessageFeedItem } from '../types';
import { LanguageMode } from '../i18n';
import { ErrorIcon, InfoIcon, WarningIcon } from './icons';

interface CriticalMessagesFeedProps {
  messages: MessageFeedItem[];
  language: LanguageMode;
}

const levelMap = {
  info: {
    Icon: InfoIcon,
    accent: 'theme-badge-emerald',
    badge: 'theme-badge-emerald',
    line: 'bg-emerald-400/70'
  },
  warning: {
    Icon: WarningIcon,
    accent: 'theme-badge-amber',
    badge: 'theme-badge-amber',
    line: 'bg-amber-400/70'
  },
  error: {
    Icon: ErrorIcon,
    accent: 'theme-badge-rose',
    badge: 'theme-badge-rose',
    line: 'bg-rose-400/80'
  }
};

export const CriticalMessagesFeed = ({ messages, language }: CriticalMessagesFeedProps) => {
  const isZh = language === 'zh';
  return (
    <section className="glass-panel flex h-full flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b border-[color:var(--border-soft)] px-6 py-5">
        <div>
          <p className="panel-eyebrow">{isZh ? '关键消息流' : 'Critical Messages Feed'}</p>
          <h2 className="theme-title mt-2 text-2xl font-semibold">{isZh ? '系统事件与通知' : 'System Events & Notifications'}</h2>
        </div>
        <span className="theme-chip px-3 py-1 text-xs font-medium">
          {isZh ? `最近 ${messages.length} 条事件` : `${messages.length} recent events`}
        </span>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <ul className="space-y-3">
          {messages.map((message) => {
            const level = levelMap[message.level];

            return (
              <li
                key={message.id}
                className="theme-card-muted relative overflow-hidden p-4"
              >
                <div className={`absolute inset-y-4 left-0 w-1 rounded-full ${level.line}`} />
                <div className="flex items-start gap-4 pl-3">
                  <div className={`theme-subtle-card mt-1 flex h-11 w-11 items-center justify-center ${level.accent}`}>
                    <level.Icon />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="theme-title text-base font-semibold">{message.title}</h3>
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${level.badge}`}>
                        {isZh ? (message.level === 'info' ? '信息' : message.level === 'warning' ? '警告' : '错误') : message.level}
                      </span>
                    </div>
                    <p className="theme-copy mt-2 text-sm leading-6">{message.message}</p>
                    <div className="theme-muted mt-3 flex flex-wrap gap-3 text-xs uppercase tracking-[0.18em]">
                      <span>{message.source}</span>
                      <span>{message.timestamp}</span>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
};
