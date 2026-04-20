import { SectionCard } from '../components/SectionCard';

const settingsGroups = [
  {
    title: 'Appearance',
    items: [
      'Switch between dark mode and light mode',
      'Keep the current theme saved after refresh',
      'Use clear contrast for cards, charts, and labels'
    ]
  },
  {
    title: 'Layout',
    items: [
      'Keep the sidebar fixed on the left',
      'Show metrics, topology, and messages in a clean vertical flow',
      'Preserve responsive spacing on smaller screens'
    ]
  },
  {
    title: 'Notifications',
    items: [
      'Highlight important system messages clearly',
      'Separate info, warning, and error states visually',
      'Keep recent activity easy to scan at a glance'
    ]
  }
];

export const SettingsPage = () => {
  return (
    <SectionCard
      eyebrow="Settings"
      title="Dashboard Settings"
      description="General interface options for theme, layout, and how information is presented."
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
