'use client';

import { Box, Circle, Hash, Link2 } from 'lucide-react';
import type { GraphNode } from './types';

export interface IndividualDetailPanelProps {
  node: GraphNode;
  dataProperties: { predicate: string; value: string }[];
  objectProperties: { predicate: string; targetId: string; targetLabel: string }[];
}

export function IndividualDetailPanel({
  node,
  dataProperties,
  objectProperties,
}: IndividualDetailPanelProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mb-6">
        <div className="mb-2 flex items-start gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-orange-100 dark:bg-orange-900/30">
            <Circle size={20} className="text-orange-500" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">{node.label}</h2>
            <p
              className="truncate font-mono text-xs text-muted-foreground"
              title={node.id}
            >
              {node.id}
            </p>
          </div>
        </div>
        <div className="ml-13 flex items-center gap-2">
          <Box size={14} className="text-blue-500" />
          <span className="text-sm text-muted-foreground">{node.type}</span>
        </div>
      </div>

      <div className="mb-6">
        <h3 className="mb-3 flex items-center gap-2 font-medium">
          <Hash size={16} className="text-purple-500" />
          Data Properties
          <span className="text-xs text-muted-foreground">({dataProperties.length})</span>
        </h3>
        {dataProperties.length === 0 ? (
          <p className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
            No data properties.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr>
                  <th className="w-2/5 px-4 py-2 text-left font-medium text-muted-foreground">
                    Property
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody>
                {dataProperties.map(({ predicate, value }, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-4 py-2 font-medium text-purple-600 dark:text-purple-400">
                      {predicate}
                    </td>
                    <td className="break-all px-4 py-2 text-muted-foreground">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-3 flex items-center gap-2 font-medium">
          <Link2 size={16} className="text-green-500" />
          Object Properties
          <span className="text-xs text-muted-foreground">({objectProperties.length})</span>
        </h3>
        {objectProperties.length === 0 ? (
          <p className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
            No object properties.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr>
                  <th className="w-2/5 px-4 py-2 text-left font-medium text-muted-foreground">
                    Property
                  </th>
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody>
                {objectProperties.map(({ predicate, targetId, targetLabel }, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-4 py-2 font-medium text-green-600 dark:text-green-400">
                      {predicate}
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-medium">{targetLabel}</span>
                      {targetLabel !== targetId && (
                        <span
                          className="mt-0.5 block truncate font-mono text-xs text-muted-foreground"
                          title={targetId}
                        >
                          {targetId}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
