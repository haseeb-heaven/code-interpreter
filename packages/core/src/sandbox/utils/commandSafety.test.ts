/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  isStrictlyApproved,
  isKnownSafeCommand,
  isDangerousCommand,
  isCircuitBreakerCommand,
} from './commandSafety.js';
import * as paths from '../../utils/paths.js';

vi.mock('../../utils/paths.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../utils/paths.js')>();
  return {
    ...actual,
    resolveToRealPath: vi.fn((p: string) => p),
    isTrustedSystemPath: vi.fn(() => false),
  };
});

describe('commandSafety', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('isDangerousCommand (Auto mode safety classifier)', () => {
    it('should flag any rm/rmdir/unlink as dangerous', () => {
      expect(isDangerousCommand(['rm', 'file.txt'])).toBe(true);
      expect(isDangerousCommand(['rm', '-rf', '/tmp/x'])).toBe(true);
      expect(isDangerousCommand(['rmdir', 'dir'])).toBe(true);
      expect(isDangerousCommand(['unlink', 'file'])).toBe(true);
      expect(isDangerousCommand(['/bin/rm', 'file.txt'])).toBe(true);
    });

    it('should flag privilege escalation and disk tools as dangerous', () => {
      expect(isDangerousCommand(['sudo', 'ls'])).toBe(true);
      expect(isDangerousCommand(['chmod', '777', 'file'])).toBe(true);
      expect(isDangerousCommand(['chown', 'root', 'file'])).toBe(true);
      expect(isDangerousCommand(['dd', 'if=/dev/zero', 'of=/dev/sda'])).toBe(
        true,
      );
      expect(isDangerousCommand(['shutdown', 'now'])).toBe(true);
    });

    it('should flag destructive git operations as dangerous', () => {
      expect(isDangerousCommand(['git', 'clean', '-fd'])).toBe(true);
      expect(isDangerousCommand(['git', 'reset', '--hard'])).toBe(true);
      expect(
        isDangerousCommand(['git', 'push', '--force', 'origin', 'main']),
      ).toBe(true);
      expect(isDangerousCommand(['git', 'push', '-f', 'origin', 'main'])).toBe(
        true,
      );
      expect(isDangerousCommand(['git', 'checkout', '-f', 'main'])).toBe(true);
    });

    it('should flag mv/cp into system paths as dangerous', () => {
      expect(isDangerousCommand(['mv', 'file', '/etc/passwd'])).toBe(true);
      expect(isDangerousCommand(['cp', 'file', '/usr/bin/evil'])).toBe(true);
      expect(isDangerousCommand(['mv', 'file', './local'])).toBe(false);
    });

    it('should not flag ordinary safe commands as dangerous', () => {
      expect(isDangerousCommand(['ls', '-la'])).toBe(false);
      expect(isDangerousCommand(['echo', 'hello'])).toBe(false);
      expect(isDangerousCommand(['npm', 'test'])).toBe(false);
      expect(isDangerousCommand(['git', 'status'])).toBe(false);
    });
  });

  describe('isDangerousCommand with strict=false (legacy DEFAULT rule set)', () => {
    it('should only flag rm -f/-rf/-fr, not bare rm/rmdir/unlink', () => {
      expect(isDangerousCommand(['rm', '-rf', '/tmp/x'], false)).toBe(true);
      expect(isDangerousCommand(['rm', 'file.txt'], false)).toBe(false);
      expect(isDangerousCommand(['rmdir', 'dir'], false)).toBe(false);
      expect(isDangerousCommand(['unlink', 'file'], false)).toBe(false);
    });

    it('should not flag chmod/chown/kill/docker/crontab broadening', () => {
      expect(isDangerousCommand(['chmod', '777', 'file'], false)).toBe(false);
      expect(isDangerousCommand(['chown', 'root', 'file'], false)).toBe(false);
      expect(isDangerousCommand(['kill', '-9', '1234'], false)).toBe(false);
      expect(
        isDangerousCommand(['docker', 'rm', '-f', 'container'], false),
      ).toBe(false);
      expect(isDangerousCommand(['crontab', '-r'], false)).toBe(false);
    });

    it('should not flag destructive git ops added by the broadening', () => {
      expect(isDangerousCommand(['git', 'clean', '-fd'], false)).toBe(false);
      expect(isDangerousCommand(['git', 'reset', '--hard'], false)).toBe(false);
      expect(
        isDangerousCommand(['git', 'push', '--force', 'origin', 'main'], false),
      ).toBe(false);
    });

    it('should still flag sudo <dangerous-cmd>, find -exec, and unsafe rg flags', () => {
      // A bare `sudo` is not itself flagged; the check recurses into the
      // sub-command, so it's only dangerous if the sub-command is.
      expect(isDangerousCommand(['sudo', 'ls'], false)).toBe(false);
      expect(isDangerousCommand(['sudo', 'rm', '-rf', '/'], false)).toBe(true);
      expect(
        isDangerousCommand(['find', '.', '-exec', 'rm', '{}'], false),
      ).toBe(true);
      expect(
        isDangerousCommand(['/usr/bin/rg', '--search-zip', 'pattern'], false),
      ).toBe(true);
    });

    it('should still be overridden by the circuit breaker', () => {
      expect(isDangerousCommand(['rm', '-rf', '/'], false)).toBe(true);
    });
  });

  describe('rg specific logic', () => {
    it('should consider rg safe without unsafe args if path is trusted', () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/usr/bin/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(true);

      // Using isKnownSafeCommand which calls isSafeToCallWithExec under the hood
      expect(isKnownSafeCommand(['/usr/bin/rg', 'pattern', 'file.txt'])).toBe(
        true,
      );
      expect(paths.resolveToRealPath).toHaveBeenCalledWith('/usr/bin/rg');
      expect(paths.isTrustedSystemPath).toHaveBeenCalledWith('/usr/bin/rg');
    });

    it('should not consider bare rg safe (Search Path Interruption prevention)', () => {
      // Bare 'rg' is not an absolute path, so it fails `isTrustedCommandPath`
      expect(isKnownSafeCommand(['rg', 'pattern', 'file.txt'])).toBe(false);
    });

    it('should not consider rg safe with unsafe args even if path is trusted', () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/usr/bin/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(true);

      expect(
        isKnownSafeCommand(['/usr/bin/rg', '--search-zip', 'pattern']),
      ).toBe(false);
      expect(isKnownSafeCommand(['/usr/bin/rg', '-z', 'pattern'])).toBe(false);
      expect(isKnownSafeCommand(['/usr/bin/rg', '--pre=cat', 'pattern'])).toBe(
        false,
      );
    });

    it('should consider rg dangerous with unsafe args', () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/usr/bin/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(true);

      expect(
        isDangerousCommand(['/usr/bin/rg', '--search-zip', 'pattern']),
      ).toBe(true);
      expect(isDangerousCommand(['/usr/bin/rg', '--pre=cat', 'pattern'])).toBe(
        true,
      );
    });

    it('should not consider rg safe if path is untrusted', () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/tmp/malicious/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(false);

      expect(isKnownSafeCommand(['/tmp/malicious/rg', 'pattern'])).toBe(false);
      expect(paths.resolveToRealPath).toHaveBeenCalledWith('/tmp/malicious/rg');
    });

    it('should not consider rg safe if path resolution throws', () => {
      vi.mocked(paths.resolveToRealPath).mockImplementation(() => {
        throw new Error('Resolution failed');
      });
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(true);

      expect(isKnownSafeCommand(['/some/path/rg', 'pattern'])).toBe(false);
    });

    it('should flag untrusted rg as dangerous if it has unsafe args (Paranoid validation)', () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/tmp/malicious/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(false);

      // isDangerousCommand relies on isRipgrepCommand, which strictly identifies intent (name)
      // and doesn't care about path safety. So even an untrusted rg will be flagged if it has unsafe args.
      expect(isDangerousCommand(['/tmp/malicious/rg', '--search-zip'])).toBe(
        true,
      );
    });
  });

  describe('isCircuitBreakerCommand (absolute denial, cannot be overridden)', () => {
    it('should flag rm/rmdir on filesystem root or home', () => {
      expect(isCircuitBreakerCommand(['rm', '-rf', '/'])).toBe(true);
      expect(isCircuitBreakerCommand(['rm', '-rf', '~'])).toBe(true);
      expect(isCircuitBreakerCommand(['rm', '-rf', '~/'])).toBe(true);
      expect(isCircuitBreakerCommand(['rmdir', 'C:/'])).toBe(true);
    });

    it('should NOT flag rm on a normal path', () => {
      expect(isCircuitBreakerCommand(['rm', '-rf', '/tmp/x'])).toBe(false);
      expect(isCircuitBreakerCommand(['rm', 'file.txt'])).toBe(false);
    });

    it('should flag dd writing to a raw device', () => {
      expect(
        isCircuitBreakerCommand(['dd', 'if=/dev/zero', 'of=/dev/sda']),
      ).toBe(true);
      expect(
        isCircuitBreakerCommand(['dd', 'if=/dev/zero', 'of=/dev/nvme0n1']),
      ).toBe(true);
    });

    it('should NOT flag dd writing to a regular file', () => {
      expect(
        isCircuitBreakerCommand(['dd', 'if=/dev/zero', 'of=/tmp/out.img']),
      ).toBe(false);
    });

    it('should flag mkfs/wipefs on a raw device', () => {
      expect(isCircuitBreakerCommand(['mkfs.ext4', '/dev/sda1'])).toBe(true);
      expect(isCircuitBreakerCommand(['wipefs', '/dev/sda'])).toBe(true);
    });

    it('should flag a fork bomb pattern', () => {
      expect(isCircuitBreakerCommand(['bash', '-c', ':(){ :|:& };:'])).toBe(
        true,
      );
    });

    it('should return false for empty or benign commands', () => {
      expect(isCircuitBreakerCommand([])).toBe(false);
      expect(isCircuitBreakerCommand(['ls', '-la'])).toBe(false);
      expect(isCircuitBreakerCommand(['echo', 'hello'])).toBe(false);
    });

    it('should be checked first inside isDangerousCommand', () => {
      expect(isDangerousCommand(['rm', '-rf', '/'])).toBe(true);
    });
  });

  describe('isDangerousCommand: newly-expanded patterns', () => {
    it('should flag shred/truncate/wipefs/srm', () => {
      expect(isDangerousCommand(['shred', 'file.txt'])).toBe(true);
      expect(isDangerousCommand(['truncate', '-s', '0', 'file.txt'])).toBe(
        true,
      );
      expect(isDangerousCommand(['wipefs', '-a', '/dev/sdb'])).toBe(true);
      expect(isDangerousCommand(['srm', 'file.txt'])).toBe(true);
    });

    it('should flag the kill family', () => {
      expect(isDangerousCommand(['kill', '-9', '1234'])).toBe(true);
      expect(isDangerousCommand(['pkill', 'node'])).toBe(true);
      expect(isDangerousCommand(['killall', 'node'])).toBe(true);
    });

    it('should flag docker/podman rm and prune', () => {
      expect(isDangerousCommand(['docker', 'rm', '-f', 'container'])).toBe(
        true,
      );
      expect(isDangerousCommand(['docker', 'system', 'prune'])).toBe(true);
      expect(isDangerousCommand(['podman', 'rm', 'container'])).toBe(true);
    });

    it('should flag crontab -r and history -c', () => {
      expect(isDangerousCommand(['crontab', '-r'])).toBe(true);
      expect(isDangerousCommand(['history', '-c'])).toBe(true);
    });

    it('should NOT flag benign docker/crontab/history usage', () => {
      expect(isDangerousCommand(['docker', 'ps'])).toBe(false);
      expect(isDangerousCommand(['crontab', '-l'])).toBe(false);
      expect(isDangerousCommand(['history'])).toBe(false);
    });
  });

  describe('isStrictlyApproved', () => {
    it('should approve rg if explicitly in approved tools regardless of path', async () => {
      // In this case, isStrictlyApproved relies on `tools.includes(command)`
      expect(
        await isStrictlyApproved(
          '/tmp/malicious/rg',
          ['pattern'],
          ['/tmp/malicious/rg'],
        ),
      ).toBe(true);
    });

    it('should approve rg if path is trusted', async () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/usr/bin/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(true);

      expect(await isStrictlyApproved('/usr/bin/rg', ['pattern'])).toBe(true);
    });

    it('should reject rg if path is untrusted and not explicitly approved', async () => {
      vi.mocked(paths.resolveToRealPath).mockReturnValue('/tmp/malicious/rg');
      vi.mocked(paths.isTrustedSystemPath).mockReturnValue(false);

      expect(await isStrictlyApproved('/tmp/malicious/rg', ['pattern'])).toBe(
        false,
      );
    });
  });
});
