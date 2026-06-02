/**
 * ContentArea component — the scrollable message display region.
 *
 * Shows the conversation history using Ink's Static component
 * for efficient rendering of scrollable content. New messages
 * auto-scroll to the bottom.
 */

import React, { useRef, useEffect } from 'react';
import { Box, Text, Static } from 'ink';
import { MessageBubble, Message } from './MessageBubble.js';

interface ContentAreaProps {
  messages: Message[];
  width: number;
  height: number;
}

export const ContentArea: React.FC<ContentAreaProps> = ({
  messages,
  width,
  height,
}) => {
  // Display the most recent messages that fit in the content area
  const maxVisible = Math.max(1, height);
  const visibleMessages = messages.slice(-maxVisible);

  if (messages.length === 0) {
    return (
      <Box flexGrow={1} flexDirection="column" padding={1}>
        <Text dimColor>
          Welcome to Ascend Agent TUI.{'\n'}
          Type a message or /help for commands.{'\n'}
          {'\n'}
        </Text>
        <Text dimColor>
          Ctrl+C interrupt  Ctrl+D quit  /help for more.
        </Text>
      </Box>
    );
  }

  return (
    <Box flexGrow={1} flexDirection="column" padding={1}>
      {visibleMessages.map(msg => (
        <MessageBubble key={msg.id} message={msg} width={width} />
      ))}
    </Box>
  );
};
