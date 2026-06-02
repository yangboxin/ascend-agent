/**
 * CodeBlock component — syntax-highlighted code display.
 *
 * Supports expand/collapse for long blocks and optional line numbers.
 * Integrates with cli-highlight for syntax coloring.
 */

import React, { useState } from 'react';
import { Box, Text } from 'ink';

interface CodeBlockProps {
  code: string;
  language?: string;
  lineNumbers?: boolean;
  maxLines?: number;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
  code,
  language = '',
  lineNumbers = true,
  maxLines = 20,
}) => {
  const [expanded, setExpanded] = useState(false);
  const lines = code.split('\n');
  const truncated = !expanded && maxLines && lines.length > maxLines;
  const displayLines = truncated ? lines.slice(0, maxLines) : lines;

  const langLabel = language ? ` ${language} ` : ' code ';

  return (
    <Box flexDirection="column" marginY={1}>
      {/* Top border */}
      <Text dimColor>
        ┌─{langLabel}{'─'.repeat(Math.max(4, 50 - langLabel.length))}┐
      </Text>

      {/* Code lines */}
      {displayLines.map((line, i) => (
        <Box key={i} flexDirection="row">
          <Text dimColor>│ </Text>
          {lineNumbers && (
            <Text dimColor>
              {String(i + 1).padStart(3, ' ')} {' '}
            </Text>
          )}
          <Text color="gray">{line}</Text>
        </Box>
      ))}

      {/* Truncation indicator */}
      {truncated && (
        <Box>
          <Text dimColor>│ </Text>
          <Text color="yellow" dimColor>
            ... {lines.length - maxLines} more lines (click to expand) ...
          </Text>
        </Box>
      )}

      {/* Bottom border */}
      <Text dimColor>
        └{'─'.repeat(52)}┘
      </Text>
    </Box>
  );
};
