'use client';
import type { ComponentProps } from 'react';
import { Header } from '@/components/shell/header';
import { GraphMenuBar } from './graph-menu-bar';
export function GraphHeader(props: ComponentProps<typeof Header>) {
  return <Header {...props} nav={<GraphMenuBar />} />;
}
