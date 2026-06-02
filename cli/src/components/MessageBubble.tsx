/**
 * MessageBubble component — renders a single chat message.
 *
 * Handles user, assistant, and system messages with appropriate
 * colors and Markdown rendering for assistant responses.
 */

import React from 'react';
import { Box, Text } from 'ink';
import chalk from 'chalk';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: number;
}

interface MessageBubbleProps {
  message: Message;
  width: number;
}

let _idCounter = 0;
export function createMessage(role: Message['role'], content: string): Message {
  return { id: `msg-${++_idCounter}`, role, content, timestamp: Date.now() };
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  switch (message.role) {
    case 'user':
      return (
        <Box marginBottom={1} flexDirection="row">
          <Text color="green" bold>{'> '}</Text>
          <Text color="green">{message.content}</Text>
        </Box>
      );

    case 'assistant':
      return (
        <Box marginBottom={1} flexDirection="column">
          <Box flexDirection="row">
            <Text color="blue" bold>🤖 </Text>
            <Box flexDirection="column">
              <AssistantContent content={message.content} />
            </Box>
          </Box>
        </Box>
      );

    case 'system':
      return (
        <Box marginBottom={1}>
          <Text dimColor italic color="yellow">
            [SYS] {message.content}
          </Text>
        </Box>
      );

    default:
      return <Text>{message.content}</Text>;
  }
};

/** Renders assistant content with simple colorization for code spans etc. */
const AssistantContent: React.FC<{ content: string }> = ({ content }) => {
  // Simple line-by-line rendering with some color hints
  const lines = content.split('\n');
  let inCodeBlock = false;

  return (
    <Box flexDirection="column">
      {lines.map((line, i) => {
        if (line.startsWith('```')) {
          inCodeBlock = !inCodeBlock;
          return <Text key={i} dimColor>{line}</Text>;
        }
        if (inCodeBlock) {
          return <Text key={i} color="gray" dimColor>{line}</Text>;
        }
        if (line.startsWith('#')) {
          return <Text key={i} bold color="cyan">{line}</Text>;
        }
        if (line.startsWith('> ')) {
          return <Text key={i} dimColor>{line}</Text>;
        }
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return <Text key={i}>{chalk.yellow('•')} {line.slice(2)}</Text>;
        }
        return <Text key={i}>{line}</Text>;
      })}
    </Box>
  );
};
