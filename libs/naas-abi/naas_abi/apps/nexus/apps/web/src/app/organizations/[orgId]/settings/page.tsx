'use client';

import { useEffect, useState } from 'react';
import { Building2, Save } from 'lucide-react';
import { useParams } from 'next/navigation';
import { cn } from '@/lib/utils';

export default function OrganizationGeneralPage() {
  const params = useParams();
  const orgId = params.orgId as string;

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const fetchOrg = async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}`);
        if (response.ok) {
          const data = await response.json();
          setName(data.name);
          setSlug(data.slug);
        }
      } catch (error) {
        console.error('Failed to fetch organization:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrg();
  }, [orgId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/organizations/${orgId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, slug }),
      });
      
      if (response.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to update organization:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">General</h2>
        <p className="text-sm text-muted-foreground">
          Manage basic organization information
        </p>
      </div>

      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <Building2 size={20} className="text-muted-foreground" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Organization Details
          </h3>
        </div>

        <div className="space-y-6">
          {/* Name */}
          <div>
            <label className="mb-2 block text-sm font-medium">
              Organization Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Corporation"
              className="w-full rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              The display name for your organization
            </p>
          </div>

          {/* Slug */}
          <div>
            <label className="mb-2 block text-sm font-medium">
              URL Slug
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                /org/
              </span>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
                placeholder="acme-corp"
                className="flex-1 rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Used in your organization's login URL
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            'flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
            saved
              ? 'bg-primary/20 text-primary'
              : 'bg-primary text-primary-foreground hover:opacity-90'
          )}
        >
          <Save size={16} />
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
