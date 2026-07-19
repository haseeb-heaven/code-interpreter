// Reads the *real* configs/models.toml so the live-testing harness always
// covers every configured model — never a hand-picked, hardcoded subset.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import TOML from '@iarna/toml';

/**
 * @param {string} repoRoot
 * @returns {Array<{ key: string, model: string, provider: string, tier: string | null }>}
 */
export function loadAllModels(repoRoot) {
  const registryPath = resolve(repoRoot, 'configs', 'models.toml');
  const data = TOML.parse(readFileSync(registryPath, 'utf8'));
  const models = data.models || {};

  return Object.entries(models).map(([key, config]) => {
    const modelId = String(config.model ?? '');
    const provider =
      typeof config.provider === 'string' && config.provider
        ? config.provider
        : modelId.includes('/')
          ? modelId.split('/')[0]
          : /^(gpt-|o[0-9](-|$))/.test(modelId)
            ? 'openai'
            : 'unknown';
    return {
      key,
      model: modelId,
      provider,
      tier: typeof config.tier === 'string' ? config.tier : null,
    };
  });
}
