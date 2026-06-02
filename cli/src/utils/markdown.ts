/**
 * Markdown-to-terminal renderer.
 *
 * Converts Markdown text into ANSI-colored strings for display in the terminal.
 * Uses `marked` for parsing and renders each token as styled text.
 */

import { marked } from 'marked';
import chalk from 'chalk';

// Type alias for marked tokens to avoid namespace issues
type MarkedToken = ReturnType<typeof marked.lexer>[number];
type InlineToken = { type: string; text?: string; tokens?: InlineToken[]; raw?: string };

/**
 * Convert a Markdown string into a plain (unstyled) string for terminal display.
 * Simple approach: strip formatting, preserve structure.
 */
export function renderMarkdown(text: string): string {
  if (!text) return '';

  try {
    const tokens = marked.lexer(text);
    return tokens.map(t => renderToken(t)).join('');
  } catch {
    // Fallback: return text as-is
    return text;
  }
}

/** Convert a marked Token to terminal-styled ANSI string */
function renderToken(token: MarkedToken): string {
  const t = token as any;

  switch (t.type) {
    case 'heading': {
      const text = t.tokens ? renderInlineTokens(t.tokens) : t.raw;
      const depth = (t as any).depth ?? 1;
      return chalk.bold.cyan('#'.repeat(depth) + ' ' + text) + '\n';
    }
    case 'paragraph': {
      const inner = t.tokens ? renderInlineTokens(t.tokens) : '';
      return inner + '\n\n';
    }
    case 'code': {
      return renderCodeBlock(t.text || '', t.lang || '');
    }
    case 'blockquote': {
      const inner = t.tokens ? t.tokens.map(renderToken).join('') : '';
      return inner.split('\n').filter((l: string) => l).map((l: string) => chalk.dim('│ ') + l).join('\n') + '\n';
    }
    case 'list': {
      const items = t.items ?? [];
      const ordered = t.ordered ?? false;
      return items.map((item: any, i: number) => {
        const prefix = ordered ? `${i + 1}. ` : '• ';
        const text = item.tokens ? renderInlineTokens(item.tokens) : item.text;
        return `  ${chalk.yellow(prefix)}${text}`;
      }).join('\n') + '\n\n';
    }
    case 'space':
      return '\n';
    case 'hr':
      return chalk.dim('─'.repeat(60)) + '\n';
    default:
      return t.raw ?? '';
  }
}

function renderInlineTokens(tokens: InlineToken[]): string {
  return tokens.map((token: InlineToken) => {
    switch (token.type) {
      case 'strong':
        return chalk.bold(renderInlineTokens(token.tokens ?? []));
      case 'em':
        return chalk.italic(renderInlineTokens(token.tokens ?? []));
      case 'codespan':
        return chalk.bgBlack.yellow(` ${token.text} `);
      case 'link':
        return chalk.blue.underline(token.text ?? '');
      case 'del':
        return chalk.strikethrough(renderInlineTokens(token.tokens ?? []));
      case 'text':
        return token.text ?? '';
      default:
        return token.raw ?? '';
    }
  }).join('');
}

function renderCodeBlock(code: string, language: string): string {
  const lines = code.split('\n');
  const langLabel = language ? ` ${language} ` : ' code ';
  let out = chalk.dim(`┌─${langLabel}${'─'.repeat(Math.max(4, 50 - langLabel.length))}┐`) + '\n';

  for (const line of lines) {
    out += chalk.dim('│ ') + chalk.gray(line) + '\n';
  }

  out += chalk.dim('└' + '─'.repeat(52) + '┘') + '\n';
  return out;
}

/**
 * Escape text for terminal display.
 */
export function sanitizeForTerminal(text: string): string {
  return text
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\t/g, '    ');
}
