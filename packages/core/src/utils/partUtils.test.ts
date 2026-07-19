/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import {
  partToString,
  getResponseText,
  flatMapTextParts,
  appendToLastTextPart,
} from './partUtils.js';
import type { GenerateContentResponse, Part, PartUnion } from '@google/genai';

const mockResponse = (
  parts?: Array<{ text?: string; functionCall?: unknown }>,
): GenerateContentResponse => ({
  candidates: parts
    ? [{ content: { parts: parts as Part[], role: 'model' }, index: 0 }]
    : [],
  promptFeedback: { safetyRatings: [] },
  text: undefined,
  data: undefined,
  functionCalls: undefined,
  executableCode: undefined,
  codeExecutionResult: undefined,
});

describe('partUtils', () => {
  describe('partToString (default behavior)', () => {
    it('should return empty string for undefined or null', () => {
      // @ts-expect-error Testing invalid input
      expect(partToString(undefined)).toBe('');
      // @ts-expect-error Testing invalid input
      expect(partToString(null)).toBe('');
    });

    it('should return string input unchanged', () => {
      expect(partToString('hello')).toBe('hello');
    });

    it('should concatenate strings from an array', () => {
      expect(partToString(['a', 'b'])).toBe('ab');
    });

    it('should return text property when provided a text part', () => {
      expect(partToString({ text: 'hi' })).toBe('hi');
    });

    it('should return empty string for non-text parts', () => {
      const part: Part = { inlineData: { mimeType: 'image/png', data: '' } };
      expect(partToString(part)).toBe('');
      const part2: Part = { functionCall: { name: 'test' } };
      expect(partToString(part2)).toBe('');
    });
  });

  describe('partToString (verbose)', () => {
    const verboseOptions = { verbose: true };

    it('should return empty string for undefined or null', () => {
      // @ts-expect-error Testing invalid input
      expect(partToString(undefined, verboseOptions)).toBe('');
      // @ts-expect-error Testing invalid input
      expect(partToString(null, verboseOptions)).toBe('');
    });

    it('should return string input unchanged', () => {
      expect(partToString('hello', verboseOptions)).toBe('hello');
    });

    it('should join parts if the value is an array', () => {
      const parts = ['hello', { text: ' world' }];
      expect(partToString(parts, verboseOptions)).toBe('hello world');
    });

    it('should return the text property if the part is an object with text', () => {
      const part: Part = { text: 'hello world' };
      expect(partToString(part, verboseOptions)).toBe('hello world');
    });

    it('should return descriptive string for videoMetadata part', () => {
      const part = { videoMetadata: {} } as Part;
      expect(partToString(part, verboseOptions)).toBe('[Video Metadata]');
    });

    it('should return descriptive string for thought part', () => {
      const part = { thought: 'thinking' } as unknown as Part;
      expect(partToString(part, verboseOptions)).toBe('[Thought: thinking]');
    });

    it('should return descriptive string for codeExecutionResult part', () => {
      const part = { codeExecutionResult: {} } as Part;
      expect(partToString(part, verboseOptions)).toBe(
        '[Code Execution Result]',
      );
    });

    it('should return descriptive string for executableCode part', () => {
      const part = { executableCode: {} } as Part;
      expect(partToString(part, verboseOptions)).toBe('[Executable Code]');
    });

    it('should return descriptive string for fileData part', () => {
      const part = { fileData: {} } as Part;
      expect(partToString(part, verboseOptions)).toBe('[File Data]');
    });

    it('should return descriptive string for functionCall part', () => {
      const part = { functionCall: { name: 'myFunction' } } as Part;
      expect(partToString(part, verboseOptions)).toBe(
        '[Function Call: myFunction]',
      );
    });

    it('should return descriptive string for functionResponse part', () => {
      const part = { functionResponse: { name: 'myFunction' } } as Part;
      expect(partToString(part, verboseOptions)).toBe(
        '[Function Response: myFunction]',
      );
    });

    it('should return descriptive string for inlineData part', () => {
      const part = { inlineData: { mimeType: 'image/png', data: '' } } as Part;
      expect(partToString(part, verboseOptions)).toBe(
        '[Image: image/png, 0.0 KB]',
      );
    });

    it('should show size for inlineData with non-empty base64 data', () => {
      // 4 base64 chars → ceil(4*3/4) = 3 bytes → 3/1024 ≈ 0.0 KB
      const part = {
        inlineData: { mimeType: 'audio/mp3', data: 'AAAA' },
      } as Part;
      expect(partToString(part, verboseOptions)).toBe(
        '[Audio: audio/mp3, 0.0 KB]',
      );
    });

    it('should return an empty string for an unknown part type', () => {
      const part: Part = {};
      expect(partToString(part, verboseOptions)).toBe('');
    });

    it('should handle complex nested arrays with various part types', () => {
      const parts = [
        'start ',
        { text: 'middle' },
        [
          { functionCall: { name: 'func1' } },
          ' end',
          { inlineData: { mimeType: 'audio/mp3', data: '' } },
        ],
      ];
      expect(partToString(parts as Part, verboseOptions)).toBe(
        'start middle[Function Call: func1] end[Audio: audio/mp3, 0.0 KB]',
      );
    });
  });

  describe('getResponseText', () => {
    it('should return null when no candidates exist', () => {
      const response = mockResponse(undefined);
      expect(getResponseText(response)).toBeNull();
    });

    it('should return concatenated text from first candidate', () => {
      const result = mockResponse([{ text: 'a' }, { text: 'b' }]);
      expect(getResponseText(result)).toBe('ab');
    });

    it('should ignore parts without text', () => {
      const result = mockResponse([{ functionCall: {} }, { text: 'hello' }]);
      expect(getResponseText(result)).toBe('hello');
    });

    it('should return null when candidate has no parts', () => {
      const result = mockResponse([]);
      expect(getResponseText(result)).toBeNull();
    });

    it('should return null if the first candidate has no content property', () => {
      const response: GenerateContentResponse = {
        candidates: [
          {
            index: 0,
          },
        ],
        promptFeedback: { safetyRatings: [] },
        text: undefined,
        data: undefined,
        functionCalls: undefined,
        executableCode: undefined,
        codeExecutionResult: undefined,
      };
      expect(getResponseText(response)).toBeNull();
    });

    it('should strip stray LLM tool-call closing tags from the tail', () => {
      const result = mockResponse([{ text: 'Done >"}</function_call>' }]);
      expect(getResponseText(result)).toBe('Done');
    });

    it('should return null when text is only a stray tool-call artifact', () => {
      const result = mockResponse([{ text: '>"}</function>' }]);
      expect(getResponseText(result)).toBeNull();
    });

    it('should not trim whitespace at chunk boundaries when called per streaming chunk', () => {
      // getResponseText is invoked once per streamed GenerateContentResponse
      // chunk (see Turn's streaming loop). A blanket .trim() here would
      // silently eat a space/newline that lands at a chunk boundary,
      // corrupting the reassembled message (e.g. merging markdown table
      // rows or words together).
      const chunk1 = mockResponse([{ text: '|level1|2|\n' }]);
      const chunk2 = mockResponse([{ text: '|level1\\ai|37|\n' }]);
      const joined =
        (getResponseText(chunk1) ?? '') + (getResponseText(chunk2) ?? '');
      expect(joined).toBe('|level1|2|\n|level1\\ai|37|\n');

      const wordChunk1 = mockResponse([{ text: 'Hello ' }]);
      const wordChunk2 = mockResponse([{ text: 'world' }]);
      const joinedWords =
        (getResponseText(wordChunk1) ?? '') +
        (getResponseText(wordChunk2) ?? '');
      expect(joinedWords).toBe('Hello world');
    });
  });

  describe('flatMapTextParts', () => {
    // A simple async transform function that splits a string into character parts.
    const splitCharsTransform = async (text: string): Promise<PartUnion[]> =>
      text.split('').map((char) => ({ text: char }));

    it('should return an empty array for empty input', async () => {
      const result = await flatMapTextParts([], splitCharsTransform);
      expect(result).toEqual([]);
    });

    it('should transform a simple string input', async () => {
      const result = await flatMapTextParts('hi', splitCharsTransform);
      expect(result).toEqual([{ text: 'h' }, { text: 'i' }]);
    });

    it('should transform a single text part object', async () => {
      const result = await flatMapTextParts(
        { text: 'cat' },
        splitCharsTransform,
      );
      expect(result).toEqual([{ text: 'c' }, { text: 'a' }, { text: 't' }]);
    });

    it('should transform an array of text parts and flatten the result', async () => {
      // A transform that duplicates the text to test the "flatMap" behavior.
      const duplicateTransform = async (text: string): Promise<PartUnion[]> => [
        { text: `${text}` },
        { text: `${text}` },
      ];
      const parts = [{ text: 'a' }, { text: 'b' }];
      const result = await flatMapTextParts(parts, duplicateTransform);
      expect(result).toEqual([
        { text: 'a' },
        { text: 'a' },
        { text: 'b' },
        { text: 'b' },
      ]);
    });

    it('should pass through non-text parts unmodified', async () => {
      const nonTextPart: Part = { functionCall: { name: 'do_stuff' } };
      const result = await flatMapTextParts(nonTextPart, splitCharsTransform);
      expect(result).toEqual([nonTextPart]);
    });

    it('should handle a mix of text and non-text parts in an array', async () => {
      const nonTextPart: Part = {
        inlineData: { mimeType: 'image/jpeg', data: '' },
      };
      const parts: PartUnion[] = [{ text: 'go' }, nonTextPart, ' stop'];
      const result = await flatMapTextParts(parts, splitCharsTransform);
      expect(result).toEqual([
        { text: 'g' },
        { text: 'o' },
        nonTextPart, // Should be passed through
        { text: ' ' },
        { text: 's' },
        { text: 't' },
        { text: 'o' },
        { text: 'p' },
      ]);
    });

    it('should handle a transform that returns an empty array', async () => {
      const removeTransform = async (_text: string): Promise<PartUnion[]> => [];
      const parts: PartUnion[] = [
        { text: 'remove' },
        { functionCall: { name: 'keep' } },
      ];
      const result = await flatMapTextParts(parts, removeTransform);
      expect(result).toEqual([{ functionCall: { name: 'keep' } }]);
    });
  });

  describe('appendToLastTextPart', () => {
    it('should append to an empty prompt', () => {
      const prompt: PartUnion[] = [];
      const result = appendToLastTextPart(prompt, 'new text');
      expect(result).toEqual([{ text: 'new text' }]);
    });

    it('should append to a prompt with a string as the last part', () => {
      const prompt: PartUnion[] = ['first part'];
      const result = appendToLastTextPart(prompt, 'new text');
      expect(result).toEqual(['first part\n\nnew text']);
    });

    it('should append to a prompt with a text part object as the last part', () => {
      const prompt: PartUnion[] = [{ text: 'first part' }];
      const result = appendToLastTextPart(prompt, 'new text');
      expect(result).toEqual([{ text: 'first part\n\nnew text' }]);
    });

    it('should append a new text part if the last part is not a text part', () => {
      const nonTextPart: Part = { functionCall: { name: 'do_stuff' } };
      const prompt: PartUnion[] = [nonTextPart];
      const result = appendToLastTextPart(prompt, 'new text');
      expect(result).toEqual([nonTextPart, { text: '\n\nnew text' }]);
    });

    it('should not append anything if the text to append is empty', () => {
      const prompt: PartUnion[] = ['first part'];
      const result = appendToLastTextPart(prompt, '');
      expect(result).toEqual(['first part']);
    });

    it('should use a custom separator', () => {
      const prompt: PartUnion[] = ['first part'];
      const result = appendToLastTextPart(prompt, 'new text', '---');
      expect(result).toEqual(['first part---new text']);
    });
  });
});
