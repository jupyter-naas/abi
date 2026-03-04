'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { CreditCard, Check, Zap, Building2, Sparkles, AlertCircle, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: '$0',
    period: '/month',
    description: 'For individuals getting started',
    features: [
      '1 workspace',
      '100 AI messages/month',
      'Community support',
      'Basic integrations',
    ],
    icon: Sparkles,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '$29',
    period: '/month',
    description: 'For professionals and small teams',
    features: [
      '5 workspaces',
      'Unlimited AI messages',
      'Priority support',
      'All integrations',
      'API access',
      'Custom agents',
    ],
    icon: Zap,
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'For organizations at scale',
    features: [
      'Unlimited workspaces',
      'Unlimited everything',
      'Dedicated support',
      'Custom integrations',
      'SSO & SAML',
      'On-premise option',
      'SLA guarantee',
    ],
    icon: Building2,
  },
];

export default function OrganizationBillingPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  
  const [currentPlan, setCurrentPlan] = useState<string>('free');
  const [usage, setUsage] = useState<{ used: number; limit: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch billing info
  useEffect(() => {
    const fetchBillingInfo = async () => {
      if (!orgId) return;
      
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}/billing`);
        
        if (!response.ok) {
          const data = await response.json();
          // Don't show error for "not implemented" message
          if (response.status === 501) {
            console.log('Billing not implemented yet:', data.detail);
            return;
          }
          throw new Error(data.detail || 'Failed to fetch billing info');
        }
        
        const data = await response.json();
        setCurrentPlan(data.plan || 'free');
        setUsage(data.usage);
      } catch (err: any) {
        console.error('Failed to fetch billing:', err);
      }
    };

    fetchBillingInfo();
  }, [orgId]);

  const handleUpgrade = async (planId: string) => {
    if (!orgId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/organizations/${orgId}/billing/upgrade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: planId }),
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to upgrade plan');
      }
      
      // Success - refresh billing info
      setCurrentPlan(planId);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddPaymentMethod = async () => {
    if (!orgId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/organizations/${orgId}/billing/payment-method`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to add payment method');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Billing & Subscription</h2>
        <p className="text-sm text-muted-foreground">
          Manage your organization&apos;s subscription and billing
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
              <div>
                <p className="font-medium text-red-500">Feature Not Available</p>
                <p className="text-sm text-red-500/90 mt-1">{error}</p>
              </div>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-600"
            >
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      {/* Current plan */}
      <div className="rounded-xl border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current Plan</p>
            <h3 className="text-2xl font-bold capitalize">{currentPlan}</h3>
          </div>
          {usage && (
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Usage this month</p>
              <p className="text-lg font-semibold">
                {usage.used} / {usage.limit} messages
              </p>
            </div>
          )}
        </div>
        {usage && (
          <div className="mt-4 h-2 rounded-full bg-secondary">
            <div
              className="h-2 rounded-full bg-primary"
              style={{ width: `${(usage.used / usage.limit) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* Plans */}
      <div>
        <h3 className="mb-4 font-semibold">Available Plans</h3>
        <div className="grid gap-4 md:grid-cols-3">
          {plans.map((plan) => {
            const Icon = plan.icon;
            const isCurrent = plan.id === currentPlan;
            return (
              <div
                key={plan.id}
                className={cn(
                  'relative rounded-xl border bg-card p-6',
                  plan.popular && 'border-primary',
                  isCurrent && 'ring-2 ring-primary'
                )}
              >
                {plan.popular && (
                  <span className="absolute -top-3 left-4 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                    Popular
                  </span>
                )}
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h4 className="font-semibold">{plan.name}</h4>
                    <p className="text-xs text-muted-foreground">
                      {plan.description}
                    </p>
                  </div>
                </div>
                <div className="mb-4">
                  <span className="text-3xl font-bold">{plan.price}</span>
                  <span className="text-muted-foreground">{plan.period}</span>
                </div>
                <ul className="mb-6 space-y-2">
                  {plan.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Check size={16} className="text-primary" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={isCurrent || loading}
                  className={cn(
                    'w-full rounded-lg py-2 text-sm font-medium transition-colors',
                    isCurrent
                      ? 'bg-secondary text-muted-foreground'
                      : 'bg-primary text-primary-foreground hover:bg-primary/90',
                    loading && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {isCurrent ? 'Current Plan' : loading ? 'Processing...' : 'Upgrade'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Payment method */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 font-semibold">Payment Method</h3>
        <div className="flex items-center justify-between rounded-lg border bg-secondary/30 p-4">
          <div className="flex items-center gap-3">
            <CreditCard size={24} className="text-muted-foreground" />
            <div>
              <p className="font-medium">No payment method</p>
              <p className="text-sm text-muted-foreground">
                Add a payment method to upgrade
              </p>
            </div>
          </div>
          <button
            onClick={handleAddPaymentMethod}
            disabled={loading}
            className={cn(
              'rounded-lg border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary',
              loading && 'opacity-50 cursor-not-allowed'
            )}
          >
            Add Card
          </button>
        </div>
      </div>

      {/* Billing history */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 font-semibold">Billing History</h3>
        <p className="text-sm text-muted-foreground">
          No invoices yet. Your billing history will appear here after you upgrade.
        </p>
      </div>
    </div>
  );
}
