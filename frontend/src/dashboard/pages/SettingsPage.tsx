import { SectionCard } from '../components/SectionCard';
import { LanguageMode } from '../i18n';

interface SettingsPageProps {
  language: LanguageMode;
}

export const SettingsPage = ({ language }: SettingsPageProps) => {
  const isZh = language === 'zh';
  const settingsGroups = [
    {
      title: isZh ? '外观' : 'Appearance',
      items: isZh
        ? ['在浅色与深色模式之间切换', '刷新后保留当前主题', '保证卡片、图表和标签的对比度清晰']
        : ['Switch between dark mode and light mode', 'Keep the current theme saved after refresh', 'Use clear contrast for cards, charts, and labels']
    },
    {
      title: isZh ? '布局' : 'Layout',
      items: isZh
        ? ['保持左侧边栏固定', '以清晰的纵向结构展示指标、拓扑和消息', '在小屏幕上保留合理的响应式间距']
        : ['Keep the sidebar fixed on the left', 'Show metrics, topology, and messages in a clean vertical flow', 'Preserve responsive spacing on smaller screens']
    },
    {
      title: isZh ? '通知' : 'Notifications',
      items: isZh
        ? ['清晰突出重要系统消息', '从视觉上区分信息、警告和错误状态', '让最近活动一眼可扫']
        : ['Highlight important system messages clearly', 'Separate info, warning, and error states visually', 'Keep recent activity easy to scan at a glance']
    }
  ];

  return (
    <SectionCard
      eyebrow={isZh ? '设置' : 'Settings'}
      title={isZh ? '仪表盘设置' : 'Dashboard Settings'}
      description={isZh ? '用于控制主题、布局以及信息呈现方式的通用界面选项。' : 'General interface options for theme, layout, and how information is presented.'}
    >
      <div className="grid gap-4 xl:grid-cols-3">
        {settingsGroups.map((group) => (
          <div key={group.title} className="theme-card-muted p-5">
            <h3 className="theme-title text-lg font-semibold">{group.title}</h3>
            <ul className="theme-copy mt-4 space-y-3 text-sm leading-6">
              {group.items.map((item) => (
                <li key={item} className="theme-subtle-card px-4 py-3">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </SectionCard>
  );
};
