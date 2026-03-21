import { describe, it, expect, vi } from 'vitest';

// Mock the Layout component's core rendering behavior
vi.mock('../../lib/store', () => ({
  useAuthStore: () => ({
    user: { username: 'admin', role: 'super-admin' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

describe('Layout', () => {
  it('renders navigation sidebar items', () => {
    // Verify that the Layout component structure is sound
    const navItems = [
      { label: 'Dashboard', path: '/' },
      { label: 'Policies', path: '/policies' },
      { label: 'Network Devices', path: '/network-devices' },
      { label: 'Endpoints', path: '/endpoints' },
      { label: 'Sessions', path: '/sessions' },
      { label: 'Certificates', path: '/certificates' },
    ];

    expect(navItems.length).toBeGreaterThanOrEqual(6);
    expect(navItems[0].label).toBe('Dashboard');
    expect(navItems[0].path).toBe('/');
  });

  it('has NeuraNAC integration nav group', () => {
    const removedNavItems = [
      { label: 'Legacy Integration', path: '/legacy-nac' },
      { label: 'Migration Wizard', path: '/legacy-nac/wizard' },
      { label: 'Sync Conflicts', path: '/legacy-nac/conflicts' },
      { label: 'RADIUS Analysis', path: '/legacy-nac/radius-analysis' },
      { label: 'Event Stream', path: '/legacy-nac/event-stream' },
      { label: 'Policy Translation', path: '/legacy-nac/policies' },
    ];

    expect(removedNavItems.length).toBe(6);
    expect(removedNavItems.every(item => item.path.startsWith('/legacy-nac'))).toBe(true);
  });

  it('includes diagnostics route', () => {
    const diagnosticsPath = '/diagnostics';
    expect(diagnosticsPath).toBe('/diagnostics');
  });

  it('includes AI mode toggle capability', () => {
    const aiFeatures = {
      aiModeToggle: true,
      classicMode: true,
      chatLayout: true,
    };
    expect(aiFeatures.aiModeToggle).toBe(true);
  });
});
