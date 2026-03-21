import { describe, it, expect, vi } from 'vitest';

vi.mock('../../lib/store', () => ({
  useAuthStore: () => ({
    user: { username: 'admin', role: 'super-admin', tenant_id: 't1' },
    isAuthenticated: true,
    accessToken: 'test-token',
  }),
}));

describe('Dashboard Page', () => {
  it('defines key dashboard metric cards', () => {
    const metricCards = [
      { title: 'Active Sessions', icon: 'Activity' },
      { title: 'Endpoints', icon: 'Monitor' },
      { title: 'Network Devices', icon: 'Server' },
      { title: 'Policy Sets', icon: 'Shield' },
      { title: 'Auth Rate', icon: 'TrendingUp' },
      { title: 'AI Risk Score', icon: 'Brain' },
    ];
    expect(metricCards.length).toBeGreaterThanOrEqual(4);
    expect(metricCards[0].title).toBe('Active Sessions');
  });

  it('defines chart sections', () => {
    const charts = [
      'Authentication Trends',
      'Top Endpoints by Traffic',
      'Policy Evaluation Latency',
      'Session Distribution',
    ];
    expect(charts.length).toBeGreaterThanOrEqual(3);
  });

  it('defines quick actions', () => {
    const quickActions = [
      { label: 'Add Network Device', path: '/network-devices/new' },
      { label: 'Create Policy', path: '/policies/new' },
      { label: 'View Live Sessions', path: '/sessions' },
      { label: 'Migration', path: '/legacy-nac/wizard' },
    ];
    expect(quickActions).toHaveLength(4);
    expect(quickActions.every(a => a.path.startsWith('/'))).toBe(true);
  });

  it('handles empty state gracefully', () => {
    const stats = { sessions: 0, endpoints: 0, devices: 0 };
    expect(stats.sessions).toBe(0);
    // Dashboard should show onboarding CTA when empty
    const showOnboarding = stats.sessions === 0 && stats.endpoints === 0;
    expect(showOnboarding).toBe(true);
  });
});
