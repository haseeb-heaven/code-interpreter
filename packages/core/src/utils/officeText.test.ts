/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import fs from 'node:fs';
import fsPromises from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { extractDocxText, isDocxPath, wordXmlToText } from './officeText.js';
import { detectFileType, processSingleFileContent } from './fileUtils.js';
import { StandardFileSystemService } from '../services/fileSystemService.js';

/** Build a minimal DOCX (ZIP) containing only word/document.xml */
function buildMinimalDocx(paragraphs: string[]): Buffer {
  const body = paragraphs
    .map(
      (p) =>
        `<w:p><w:r><w:t>${p
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')}</w:t></w:r></w:p>`,
    )
    .join('');
  const xml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>${body}</w:body>
</w:document>`;
  const content = Buffer.from(xml, 'utf8');
  const compressed = zlib.deflateRawSync(content);
  const name = Buffer.from('word/document.xml', 'utf8');

  const localHeader = Buffer.alloc(30);
  localHeader.writeUInt32LE(0x04034b50, 0); // sig
  localHeader.writeUInt16LE(20, 4); // version
  localHeader.writeUInt16LE(0, 6); // flags
  localHeader.writeUInt16LE(8, 8); // deflate
  localHeader.writeUInt16LE(0, 10); // time
  localHeader.writeUInt16LE(0, 12); // date
  localHeader.writeUInt32LE(0, 14); // crc (0 ok for readers that ignore)
  localHeader.writeUInt32LE(compressed.length, 18);
  localHeader.writeUInt32LE(content.length, 22);
  localHeader.writeUInt16LE(name.length, 26);
  localHeader.writeUInt16LE(0, 28); // extra

  // Central directory + EOCD so the archive is well-formed (reader only needs local headers)
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(20, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt16LE(0, 8);
  central.writeUInt16LE(8, 10);
  central.writeUInt16LE(0, 12);
  central.writeUInt16LE(0, 14);
  central.writeUInt32LE(0, 16);
  central.writeUInt32LE(compressed.length, 20);
  central.writeUInt32LE(content.length, 24);
  central.writeUInt16LE(name.length, 28);
  central.writeUInt16LE(0, 30);
  central.writeUInt16LE(0, 32);
  central.writeUInt16LE(0, 34);
  central.writeUInt16LE(0, 36);
  central.writeUInt32LE(0, 38);
  central.writeUInt32LE(0, 42); // relative offset of local header

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(1, 8);
  eocd.writeUInt16LE(1, 10);
  eocd.writeUInt32LE(46 + name.length, 12);
  eocd.writeUInt32LE(30 + name.length + compressed.length, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([localHeader, name, compressed, central, name, eocd]);
}

describe('officeText', () => {
  it('isDocxPath recognizes .docx only', () => {
    expect(isDocxPath('a/b/c.DOCX')).toBe(true);
    expect(isDocxPath('notes.doc')).toBe(false);
    expect(isDocxPath('notes.txt')).toBe(false);
  });

  it('wordXmlToText strips tags and keeps paragraphs', () => {
    const xml = `<w:p><w:r><w:t>Hello</w:t></w:r></w:p><w:p><w:r><w:t>World &amp; Co</w:t></w:r></w:p>`;
    expect(wordXmlToText(xml)).toBe('Hello\nWorld & Co');
  });

  describe('extractDocxText + processSingleFileContent', () => {
    let dir: string;
    let docxPath: string;

    beforeAll(async () => {
      dir = await fsPromises.mkdtemp(path.join(os.tmpdir(), 'docx-test-'));
      docxPath = path.join(dir, 'sample.docx');
      await fsPromises.writeFile(
        docxPath,
        buildMinimalDocx(['Mock Document Header', 'Key Features']),
      );
    });

    afterAll(async () => {
      await fsPromises.rm(dir, { recursive: true, force: true });
    });

    it('extracts paragraph text from a minimal docx', async () => {
      const text = await extractDocxText(docxPath);
      expect(text).toContain('Mock Document Header');
      expect(text).toContain('Key Features');
    });

    it('detectFileType returns docx', async () => {
      expect(await detectFileType(docxPath)).toBe('docx');
    });

    it('processSingleFileContent returns extracted text', async () => {
      const result = await processSingleFileContent(
        docxPath,
        dir,
        new StandardFileSystemService(),
      );
      expect(result.error).toBeUndefined();
      expect(String(result.llmContent)).toContain('Mock Document Header');
      expect(String(result.returnDisplay)).toMatch(/DOCX/i);
    });
  });

  it('extracts text from the real demo_word.docx when present', async () => {
    const real = 'D:\\tmp\\dummy_media\\documents\\demo_word.docx';
    if (!fs.existsSync(real)) {
      return;
    }
    const text = await extractDocxText(real);
    expect(text.toLowerCase()).toMatch(/mock document|word|structured/);
  });
});
