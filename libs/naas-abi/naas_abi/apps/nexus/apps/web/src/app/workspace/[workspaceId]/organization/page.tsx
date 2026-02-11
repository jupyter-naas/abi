'use client';

import { useState, useEffect } from 'react';
import { Save, Building2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOrganizationStore } from '@/stores/organization';

export default function OrganizationGeneralPage() {
  const { organizations, fetchOrganizations, updateOrganization } = useOrganizationStore();
  const org = organizations[0]; // Primary org

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchOrganizations();
  }, [fetchOrganizations]);

  useEffect(() => {
    if (org) {
      setName(org.name);
      setSlug(org.slug);
    }
  }, [org]);

  const handleSave = async () => {
    if (!org) return;
    setLoading(true);
    await updateOrganization(org.id, { name, slug });
    setLoading(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!org) {
    return (
      <div className="text-center text-muted-foreground py-12">
        Loading organization...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">General</h2>
        <p className="text-sm text-muted-foreground">
          Manage your organization&apos;s basic information
        </p>
      </div>

      {/* Org icon */}
      <div className="flex items-center gap-4">
        <div
          className="flex h-16 w-16 items-center justify-center rounded-xl text-white font-bold text-2xl"
          style={{ backgroundColor: org.primaryColor || '#22c55e' }}
        >
          {org.logoEmoji || org.name.charAt(0).toUpperCase()}
        </div>
        <div>
          <h3 className="font-medium">{org.name}</h3>
          <p className="text-sm text-muted-foreground">/{org.slug}</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Organization Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Slug</label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Login URL: nexus.app/org/{slug}/auth/login
            </p>
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={loading}
          className={cn(
            'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
            saved
              ? 'bg-blue-500/20 text-blue-500'
              : 'bg-blue-500 text-white hover:bg-blue-600'
          )}
        >
          <Save size={16} />
          {saved ? 'Saved!' : loading ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
