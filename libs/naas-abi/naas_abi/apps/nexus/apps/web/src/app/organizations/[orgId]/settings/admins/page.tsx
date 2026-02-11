'use client';

import { Plus, Shield, Crown, UserCircle } from 'lucide-react';

export default function OrgAdminsPage() {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Admins</h2>
          <p className="text-sm text-muted-foreground">
            Manage who can administer this organization
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors">
          <Plus size={16} />
          Add Admin
        </button>
      </div>

      <div className="rounded-xl border bg-card">
        <div className="border-b px-4 py-3">
          <p className="text-sm font-medium text-muted-foreground">Organization Admins</p>
        </div>
        <div className="divide-y">
          {[
            { name: 'Alice Johnson', email: 'alice@example.com', role: 'owner' },
            { name: 'Bob Smith', email: 'bob@example.com', role: 'admin' },
          ].map((admin) => (
            <div key={admin.email} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
                  <UserCircle size={20} />
                </div>
                <div>
                  <p className="text-sm font-medium">{admin.name}</p>
                  <p className="text-xs text-muted-foreground">{admin.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {admin.role === 'owner' && (
                  <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-500">
                    <Crown size={12} />
                    Owner
                  </span>
                )}
                {admin.role === 'admin' && (
                  <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-500">
                    <Shield size={12} />
                    Admin
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-center text-xs text-muted-foreground">
        Admin management coming soon
      </p>
    </div>
  );
}
