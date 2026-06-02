/**
 * Hook: streaming response handler.
 *
 * Manages state for receiving and displaying streaming AI responses:
 * - Appending chunks to the last assistant message (typewriter effect)
 * - Interrupting an in-progress stream
 * - Completion detection
 */

import { useState, useCallback, useRef } from 'react';

export interface StreamState {
  isStreaming: boolean;
  chunkCount: number;
  totalChars: number;
  elapsed: number;
}

export function useStreamingResponse(
  onChunk: (text: string) => void,
  onComplete: () => void,
  onError: (error: Error) => void,
) {
  const [streamState, setStreamState] = useState<StreamState>({
    isStreaming: false,
    chunkCount: 0,
    totalChars: 0,
    elapsed: 0,
  });
  const interruptRef = useRef(false);
  const startTimeRef = useRef(0);

  const startStream = useCallback(() => {
    interruptRef.current = false;
    startTimeRef.current = Date.now();
    setStreamState({
      isStreaming: true,
      chunkCount: 0,
      totalChars: 0,
      elapsed: 0,
    });
  }, []);

  const pushChunk = useCallback((text: string) => {
    if (interruptRef.current) return;
    onChunk(text);
    setStreamState(prev => ({
      ...prev,
      chunkCount: prev.chunkCount + 1,
      totalChars: prev.totalChars + text.length,
      elapsed: (Date.now() - startTimeRef.current) / 1000,
    }));
  }, [onChunk]);

  const finishStream = useCallback(() => {
    setStreamState(prev => ({
      ...prev,
      isStreaming: false,
      elapsed: (Date.now() - startTimeRef.current) / 1000,
    }));
    onComplete();
  }, [onComplete]);

  const requestInterrupt = useCallback(() => {
    interruptRef.current = true;
  }, []);

  const handleError = useCallback((error: Error) => {
    setStreamState(prev => ({ ...prev, isStreaming: false }));
    onError(error);
  }, [onError]);

  /** Consume an async iterable stream and push chunks. */
  const consumeStream = useCallback(async (
    stream: AsyncIterable<string>,
  ): Promise<void> => {
    startStream();
    try {
      for await (const chunk of stream) {
        if (interruptRef.current) break;
        pushChunk(chunk);
      }
    } catch (e) {
      handleError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      finishStream();
    }
  }, [startStream, pushChunk, finishStream, handleError]);

  /** Consume an SSE (Server-Sent Events) endpoint. */
  const consumeSSE = useCallback(async (
    url: string,
    body?: Record<string, unknown>,
  ): Promise<void> => {
    startStream();
    try {
      const response = await fetch(url, {
        method: body ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        if (interruptRef.current) break;
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              const content = parsed?.choices?.[0]?.delta?.content ?? parsed?.content ?? '';
              if (content) pushChunk(String(content));
            } catch {
              // Non-JSON data — push as-is
              if (data.trim()) pushChunk(data);
            }
          }
        }
      }
    } catch (e) {
      handleError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      finishStream();
    }
  }, [startStream, pushChunk, finishStream, handleError]);

  return {
    streamState,
    startStream,
    pushChunk,
    finishStream,
    requestInterrupt,
    consumeStream,
    consumeSSE,
  };
}
