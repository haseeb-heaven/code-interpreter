/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Lightweight Office Open XML (DOCX) text extraction.
 * DOCX is a ZIP of XML parts; we read word/document.xml without external deps.
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import zlib from 'node:zlib';
import { promisify } from 'node:util';

const inflateRaw = promisify(zlib.inflateRaw);
const inflate = promisify(zlib.inflate);

const DOCX_EXT = new Set(['.docx']);

/** True when the path looks like a Word Open XML document. */
export function isDocxPath(filePath: string): boolean {
  return DOCX_EXT.has(path.extname(filePath).toLowerCase());
}

/**
 * Minimal ZIP local-file-header walk to extract one stored/deflated entry.
 * Supports DEFLATE (8) and STORE (0) methods used by Word.
 */
async function readZipEntry(
  buffer: Buffer,
  entryName: string,
): Promise<Buffer | null> {
  const target = entryName.replace(/\\/g, '/');
  let offset = 0;

  while (offset + 30 <= buffer.length) {
    const sig = buffer.readUInt32LE(offset);
    // Local file header signature
    if (sig !== 0x04034b50) {
      // End of central directory or unexpected — stop
      break;
    }

    const compressionMethod = buffer.readUInt16LE(offset + 8);
    const generalPurpose = buffer.readUInt16LE(offset + 6);
    const hasDataDescriptor = (generalPurpose & 0x0008) !== 0;
    let compressedSize = buffer.readUInt32LE(offset + 18);
    const fileNameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const nameStart = offset + 30;
    const nameEnd = nameStart + fileNameLength;
    if (nameEnd + extraLength > buffer.length) {
      break;
    }
    const name = buffer.subarray(nameStart, nameEnd).toString('utf8');
    const dataStart = nameEnd + extraLength;
    let dataEnd = dataStart + compressedSize;

    // When sizes are in data descriptor (bit 3), compressedSize may be 0 in header.
    // Fall back to scanning for the next local header / descriptor.
    if (hasDataDescriptor && compressedSize === 0) {
      // Search forward for data descriptor signature or next local header
      const ddSig = Buffer.from([0x50, 0x4b, 0x07, 0x08]);
      let search = dataStart;
      let found = -1;
      while (search + 16 <= buffer.length) {
        const at = buffer.indexOf(ddSig, search);
        if (at === -1) break;
        // Descriptor: sig + crc + compressed + uncompressed (or without sig in some writers)
        const maybeComp = buffer.readUInt32LE(at + 8);
        if (at + 16 + maybeComp <= buffer.length || maybeComp < buffer.length) {
          // Prefer matching by checking inflated size later; accept first plausible
          found = at;
          compressedSize = maybeComp;
          dataEnd = dataStart + compressedSize;
          break;
        }
        search = at + 4;
      }
      if (found === -1) {
        // Try next local file header as boundary
        const nextLocal = buffer.indexOf(
          Buffer.from([0x50, 0x4b, 0x03, 0x04]),
          dataStart,
        );
        if (nextLocal === -1) {
          break;
        }
        dataEnd = nextLocal;
        compressedSize = dataEnd - dataStart;
      }
    }

    if (dataEnd > buffer.length) {
      break;
    }

    if (name === target || name.endsWith('/' + target)) {
      const compressed = buffer.subarray(dataStart, dataEnd);
      if (compressionMethod === 0) {
        return Buffer.from(compressed);
      }
      if (compressionMethod === 8) {
        try {
          return await inflateRaw(compressed);
        } catch {
          // Some writers use zlib-wrapped deflate
          return inflate(compressed);
        }
      }
      throw new Error(
        `Unsupported ZIP compression method ${compressionMethod} for ${name}`,
      );
    }

    // Advance: if data descriptor follows compressed data
    offset = dataEnd;
    if (hasDataDescriptor) {
      // Optional signature + 12 or 16 bytes
      if (
        offset + 4 <= buffer.length &&
        buffer.readUInt32LE(offset) === 0x08074b50
      ) {
        offset += 16; // sig + crc + csize + usize
      } else {
        offset += 12; // crc + csize + usize without sig
      }
    }
  }

  return null;
}

/**
 * Convert WordprocessingML document.xml into plain text (lossy but useful).
 */
export function wordXmlToText(xml: string): string {
  let text = xml;
  // Drop binary-ish parts
  text = text.replace(/<w:binData[\s\S]*?<\/w:binData>/gi, '');
  // Tabs and breaks
  text = text.replace(/<w:tab\b[^/]*\/>/gi, '\t');
  text = text.replace(/<w:br\b[^/]*\/>/gi, '\n');
  text = text.replace(/<w:cr\b[^/]*\/>/gi, '\n');
  // Paragraph / table row ends → newlines
  text = text.replace(/<\/w:p>/gi, '\n');
  text = text.replace(/<\/w:tr>/gi, '\n');
  text = text.replace(/<\/w:tc>/gi, '\t');
  // Strip remaining tags
  text = text.replace(/<[^>]+>/g, '');
  // Decode a few common entities
  text = text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) =>
      String.fromCharCode(parseInt(h, 16)),
    );
  // Collapse excessive blank lines
  text = text
    .split(/\r?\n/)
    .map((line) => line.replace(/[ \t]+$/g, ''))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return text;
}

/**
 * Extract plain text from a .docx file path.
 * Returns empty string when the document has no extractable body text.
 */
export async function extractDocxText(filePath: string): Promise<string> {
  const buffer = await fs.readFile(filePath);
  // ZIP magic
  if (buffer.length < 4 || buffer.readUInt32LE(0) !== 0x04034b50) {
    throw new Error('Not a valid DOCX (ZIP) archive');
  }

  const xmlBuf = await readZipEntry(buffer, 'word/document.xml');
  if (!xmlBuf) {
    throw new Error('DOCX missing word/document.xml');
  }
  const xml = xmlBuf.toString('utf8');
  return wordXmlToText(xml);
}
