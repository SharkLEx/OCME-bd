/**
 * Permission Mode System (Exec Modes)
 *
 * Controls agent autonomy level with 3 execution modes:
 * - explore (SAFETY): Read-only, safe observation
 * - ask (INTERATIVO): Confirm before changes, guided execution
 * - auto (AUTO): Full autonomy, agents operate freely
 *
 * Supports per-domain modes (multi-tenant):
 * - Global default: permissions.mode
 * - Per-domain: permissions.domains.{domain} (overrides global)
 * - Example: dev squad AUTO, marketing squad INTERATIVO
 *
 * Morpheus persona: "I can only show you the door. You're the one that has to walk through it."
 *
 * @module permissions/permission-mode
 * @version 2.1.0
 * @inspired-by Craft Agents OSS
 */

const fs = require('fs').promises;
const path = require('path');
const yaml = require('js-yaml');

class PermissionMode {
  /**
   * Available execution modes with their configurations
   */
  static MODES = {
    explore: {
      name: 'SAFETY',
      icon: '🛡️',
      color: 'blue',
      description: 'Observe. Aprenda. Quando estiver pronto, saberá o que fazer.',
      shortDescription: 'Somente leitura',
      morpheus: 'Você ainda não está pronto. Observe a Matrix antes de agir.',
      permissions: {
        read: true,
        write: false,
        execute: false,
        delete: false,
      },
    },
    ask: {
      name: 'INTERATIVO',
      icon: '💬',
      color: 'yellow',
      description: 'A escolha é sua, mas eu estarei aqui para guiar cada passo.',
      shortDescription: 'Confirma antes de agir',
      morpheus: 'Eu posso te mostrar a porta. Você é quem tem que atravessá-la.',
      permissions: {
        read: true,
        write: 'confirm',
        execute: 'confirm',
        delete: 'confirm',
      },
    },
    auto: {
      name: 'AUTO',
      icon: '⚡',
      color: 'green',
      description: 'Autonomia total — sem limites, sem hesitação.',
      shortDescription: 'Autonomia total',
      morpheus: 'Você está pronto. A Matrix é sua.',
      permissions: {
        read: true,
        write: true,
        execute: true,
        delete: true,
      },
    },
  };

  /**
   * Valid mode keys
   */
  static MODE_KEYS = ['explore', 'ask', 'auto'];

  constructor(projectRoot = process.cwd()) {
    this.projectRoot = projectRoot;
    this.configPath = path.join(projectRoot, '.lmas', 'config.yaml');
    this.currentMode = 'ask'; // global default
    this.domainModes = {}; // per-domain overrides { 'software-dev': 'auto', 'marketing': 'ask' }
    this._loaded = false;
  }

  /**
   * Load current mode from config
   * @returns {Promise<string>} Current mode name
   */
  async load() {
    if (this._loaded) return this.currentMode;

    try {
      const configContent = await fs.readFile(this.configPath, 'utf-8');
      const config = yaml.load(configContent) || {};
      this.currentMode = config.permissions?.mode || 'ask';

      // Validate global mode
      if (!PermissionMode.MODES[this.currentMode]) {
        console.warn(`Invalid mode "${this.currentMode}" in config, defaulting to "ask"`);
        this.currentMode = 'ask';
      }

      // Load per-domain modes
      const domains = config.permissions?.domains || {};
      for (const [domain, mode] of Object.entries(domains)) {
        if (PermissionMode.MODES[mode]) {
          this.domainModes[domain] = mode;
        } else {
          console.warn(`Invalid mode "${mode}" for domain "${domain}", ignoring`);
        }
      }
    } catch (_error) {
      // Config doesn't exist or is invalid, use default
      this.currentMode = 'ask';
    }

    this._loaded = true;
    return this.currentMode;
  }

  /**
   * Set permission mode (global or per-domain)
   * @param {string} mode - Mode name (explore, ask, auto) or alias
   * @param {string} [domain] - Optional domain name for per-domain mode
   * @returns {Promise<Object>} Mode info
   */
  async setMode(mode, domain = null) {
    // Handle aliases (PT-BR and EN)
    const aliases = {
      autonomo: 'auto',
      autonomia: 'auto',
      safe: 'explore',
      safety: 'explore',
      seguro: 'explore',
      seguranca: 'explore',
      balanced: 'ask',
      interativo: 'ask',
      interactive: 'ask',
      guiado: 'ask',
    };
    mode = aliases[mode] || mode;

    if (!PermissionMode.MODES[mode]) {
      const validModes = Object.keys(PermissionMode.MODES).join(', ');
      throw new Error(`Invalid mode: "${mode}". Valid modes: ${validModes}`);
    }

    if (domain) {
      // Per-domain mode
      this.domainModes[domain] = mode;
      await this._saveToConfig(null, domain, mode);
    } else {
      // Global mode
      this.currentMode = mode;
      await this._saveToConfig(mode);
    }

    this._loaded = true;
    return domain ? this.getModeInfoForDomain(domain) : this.getModeInfo();
  }

  /**
   * Get current mode information
   * @returns {Object} Mode info with name, icon, description, permissions
   */
  getModeInfo() {
    const mode = PermissionMode.MODES[this.currentMode];
    return {
      mode: this.currentMode,
      ...mode,
    };
  }

  /**
   * Get mode for a specific domain (falls back to global)
   * @param {string} domain - Domain name (e.g., 'software-dev', 'marketing')
   * @returns {string} Mode key (explore, ask, auto)
   */
  getModeForDomain(domain) {
    if (domain && this.domainModes[domain]) {
      return this.domainModes[domain];
    }
    return this.currentMode;
  }

  /**
   * Get mode info for a specific domain
   * @param {string} domain - Domain name
   * @returns {Object} Mode info with name, icon, description, permissions, domain
   */
  getModeInfoForDomain(domain) {
    const modeKey = this.getModeForDomain(domain);
    const mode = PermissionMode.MODES[modeKey];
    return {
      mode: modeKey,
      domain,
      isOverride: !!this.domainModes[domain],
      ...mode,
    };
  }

  /**
   * Get all domain mode overrides
   * @returns {Object} Map of domain → mode info
   */
  getDomainModes() {
    const result = {};
    for (const [domain, modeKey] of Object.entries(this.domainModes)) {
      const mode = PermissionMode.MODES[modeKey];
      result[domain] = { mode: modeKey, ...mode };
    }
    return result;
  }

  /**
   * Get mode badge for display in greeting
   * @param {string} [domain] - Optional domain for domain-specific badge
   * @returns {string} Formatted badge like "[⚡ AUTO]" or "[⚡ AUTO/software-dev]"
   */
  getBadge(domain = null) {
    const modeKey = domain ? this.getModeForDomain(domain) : this.currentMode;
    const mode = PermissionMode.MODES[modeKey];
    if (domain && this.domainModes[domain]) {
      return `[${mode.icon} ${mode.name}/${domain}]`;
    }
    return `[${mode.icon} ${mode.name}]`;
  }

  /**
   * Check if an operation is allowed
   * @param {string} operation - Operation type (read, write, execute, delete)
   * @param {string} [domain] - Optional domain for domain-specific check
   * @returns {Object} { allowed: boolean|'confirm', reason?: string, message?: string }
   */
  canPerform(operation, domain = null) {
    const modeKey = domain ? this.getModeForDomain(domain) : this.currentMode;
    const mode = PermissionMode.MODES[modeKey];
    const permission = mode.permissions[operation];

    if (permission === true) {
      return { allowed: true };
    }

    if (permission === false) {
      return {
        allowed: false,
        reason: `Blocked in ${mode.name} mode`,
        message: `🔒 Operation "${operation}" is blocked in ${mode.name} mode. Use \`*mode ask\` or \`*mode auto\` to enable.`,
      };
    }

    if (permission === 'confirm') {
      return {
        allowed: 'confirm',
        message: `${mode.icon} Operation "${operation}" requires confirmation in ${mode.name} mode.`,
      };
    }

    return {
      allowed: false,
      reason: 'Unknown operation type',
    };
  }

  /**
   * Check if current mode allows autonomous execution
   * @returns {boolean}
   */
  isAutonomous() {
    return this.currentMode === 'auto';
  }

  /**
   * Check if current mode is read-only
   * @returns {boolean}
   */
  isReadOnly() {
    return this.currentMode === 'explore';
  }

  /**
   * Get help text for modes
   * @returns {string} Markdown formatted help
   */
  /**
   * Get exec mode selection menu (Morpheus-style)
   * @returns {string} Markdown formatted selection menu
   */
  /**
   * Get exec mode selection menu (Morpheus-style)
   * @param {string} [domain] - Optional domain context for showing current domain mode
   * @param {Object} [domainModes] - Current domain mode overrides
   * @returns {string} Markdown formatted selection menu
   */
  static getExecMenu(domain = null, domainModes = {}) {
    let menu = '## 👑 Modo de Execução\n\n';
    menu += '*"Eu não posso te dizer o que a Matrix é. Você tem que ver por si mesmo."*\n\n';

    const entries = Object.entries(PermissionMode.MODES);
    entries.forEach(([, mode], index) => {
      menu += `**${index + 1}. ${mode.icon} ${mode.name}** — ${mode.shortDescription}\n`;
      menu += `   *${mode.morpheus}*\n\n`;
    });

    if (domain) {
      menu += `**Domínio ativo:** ${domain}\n`;
      menu += 'Escolha um modo (1-3) ou diga o nome. Aplica apenas ao domínio ativo.\n';
    } else {
      menu += 'Escolha um modo (1-3) ou diga o nome.\n';
    }

    // Show current domain overrides if any exist
    const overrides = Object.entries(domainModes);
    if (overrides.length > 0) {
      menu += '\n**Modos por domínio:**\n';
      for (const [d, modeKey] of overrides) {
        const mode = PermissionMode.MODES[modeKey];
        if (mode) {
          menu += `- ${d}: ${mode.icon} ${mode.name}\n`;
        }
      }
    }

    return menu;
  }

  static getHelp() {
    let help = '## Modos de Execução (*exec)\n\n';
    help += '| Modo | Ícone | Descrição | Escrita | Execução |\n';
    help += '|------|-------|-----------|---------|----------|\n';

    for (const [, mode] of Object.entries(PermissionMode.MODES)) {
      const writes =
        mode.permissions.write === true ? '✅' : mode.permissions.write === 'confirm' ? '💬' : '❌';
      const executes =
        mode.permissions.execute === true
          ? '✅'
          : mode.permissions.execute === 'confirm'
            ? '💬'
            : '❌';
      help += `| ${mode.name} | ${mode.icon} | ${mode.shortDescription} | ${writes} | ${executes} |\n`;
    }

    help += '\n**Comandos:**\n';
    help += '- `*exec` — Mostra menu de seleção de modo\n';
    help += '- `*exec auto` — Autonomia total\n';
    help += '- `*exec interativo` — Confirma antes de agir\n';
    help += '- `*exec safety` — Somente leitura\n';

    return help;
  }

  /**
   * Save mode to config file (global or per-domain)
   * @param {string|null} globalMode - Global mode to set (null to skip)
   * @param {string|null} domain - Domain name for per-domain mode (null for global)
   * @param {string|null} domainMode - Domain-specific mode (required if domain is set)
   * @private
   */
  async _saveToConfig(globalMode, domain = null, domainMode = null) {
    let config = {};

    // Try to read existing config
    try {
      const configContent = await fs.readFile(this.configPath, 'utf-8');
      config = yaml.load(configContent) || {};
    } catch {
      // Config doesn't exist, will create new
    }

    // Update permissions section
    config.permissions = config.permissions || {};

    if (globalMode) {
      config.permissions.mode = globalMode;
    }

    if (domain && domainMode) {
      config.permissions.domains = config.permissions.domains || {};
      config.permissions.domains[domain] = domainMode;
    }

    // Ensure .lmas directory exists
    const lmasDir = path.dirname(this.configPath);
    await fs.mkdir(lmasDir, { recursive: true });

    // Write config
    const configYaml = yaml.dump(config, { indent: 2 });
    await fs.writeFile(this.configPath, configYaml, 'utf-8');
  }
}

module.exports = { PermissionMode };
