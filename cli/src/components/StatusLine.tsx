/**
 * StatusLine component — displays session info at the top.
 *
 * Shows: provider, model, streaming indicator, elapsed time,
 * and keyboard shortcut hints.
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';

interface StatusLineProps {
  provider: string;
  model: string;
  isStreaming: boolean;
  tokenCount: number;
  elapsed: number;
  width: number;
}

export const StatusLine: React.FC<StatusLineProps> = ({
  provider,
  model,
  isStreaming,
  tokenCount,
  elapsed,
  width,
}) => {
  const leftParts: string[] = [];
  leftParts.push('ascend');
  if (provider) leftParts.push(`provider:${provider}`);
  if (model) leftParts.push(`model:${model}`);

  const rightParts: string[] = [];
  if (tokenCount > 0) rightParts.push(`tokens:${tokenCount.toLocaleString()}`);
  rightParts.push('Ctrl+C:interrupt  Ctrl+D:quit');

  const left = leftParts.join(' │ ');
  const right = rightParts.join('  ');
  const padding = Math.max(1, width - left.length - right.length - 2);

  return (
    <Box flexShrink={0} height={1}>
      <Text backgroundColor="#073642" color="#839496">
        {' '}
        <Text bold color="#b58900">ascend</Text>
        <Text color="#657b83"> │ </Text>
        {provider ? <><Text color="#2aa198">provider:{provider}</Text><Text color="#657b83">  </Text></> : null}
        {model ? <><Text color="#268bd2">model:{model}</Text><Text color="#657b83">  </Text></> : null}
        {isStreaming ? <><Text color="#859900"><Spinner type="dots" /> streaming</Text><Text color="#657b83">  </Text></> : null}
        {elapsed > 0 ? <><Text color="#6c71c4">{elapsed.toFixed(1)}s</Text><Text color="#657b83">  </Text></> : null}
        {' '.repeat(padding)}
        <Text color="#586e75">{right}</Text>
        {' '}
      </Text>
    </Box>
  );
};
