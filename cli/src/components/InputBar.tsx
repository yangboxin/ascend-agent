/**
 * InputBar component — fixed-bottom multiline input area.
 *
 * The input bar is always positioned at the bottom of the terminal.
 * Supports:
 * - Text input with Ink's TextInput
 * - Submit on Enter
 * - Visual border separating it from the content area
 */

import React from 'react';
import { Box, Text } from 'ink';
import TextInput from 'ink-text-input';

interface InputBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  placeholder?: string;
}

export const InputBar: React.FC<InputBarProps> = ({
  value,
  onChange,
  onSubmit,
}) => {
  return (
    <Box flexShrink={0} flexDirection="column">
      {/* Separator */}
      <Text dimColor>{'─'.repeat(60)}</Text>

      {/* Input area */}
      <Box flexDirection="row" paddingY={0}>
        <Text color="cyan" bold>{'> '}</Text>
        <TextInput
          value={value}
          onChange={onChange}
          onSubmit={onSubmit}
          placeholder="Type a message or /command..."
        />
      </Box>
    </Box>
  );
};
