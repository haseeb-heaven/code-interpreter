/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Canonical "OA" block logo (OpenAgent). Pure art only — version / auth
 * metadata is rendered beside it by AppHeader.
 *
 * Renders as:
 *   ██████╗  █████╗
 *  ██╔═══██╗██╔══██╗
 *  ██║   ██║███████║
 *  ██║   ██║██╔══██║
 *  ╚██████╔╝██║  ██║
 *   ╚═════╝ ╚═╝  ╚═╝
 */
export const oaAsciiLogo = `
 ██████╗  █████╗ 
██╔═══██╗██╔══██╗
██║   ██║███████║
██║   ██║██╔══██║
╚██████╔╝██║  ██║
 ╚═════╝ ╚═╝  ╚═╝
`.replace(/^\n/, '');

/** Same as {@link oaAsciiLogo} with a small indent for Header layouts. */
export const shortAsciiLogo = `
    ██████╗  █████╗
   ██╔═══██╗██╔══██╗
   ██║   ██║███████║
   ██║   ██║██╔══██║
   ╚██████╔╝██║  ██║
    ╚═════╝ ╚═╝  ╚═╝
`;

export const longAsciiLogo = shortAsciiLogo;

/** Compact two-letter OA for very narrow terminals. */
export const tinyAsciiLogo = `
█▀▀█ ▄▀█
█▄▄█ █▀█
▀  ▀ ▀ ▀
`;

/** Compact OA art (no leading indent) used by AppHeader. */
export const shortAsciiLogoCompactText = oaAsciiLogo.trimEnd();

export const longAsciiLogoCompactText = shortAsciiLogoCompactText;

export const tinyAsciiLogoCompactText = `
█▀▀█ ▄▀█
█▄▄█ █▀█
▀  ▀ ▀ ▀
`
  .replace(/^\n/, '')
  .trimEnd();
