---
type: squad
id: cybersecurity-squad
title: "🛡️ Cybersecurity-Squad — Security Specialists"
version: "1.0.0"
domain: software-dev
cssclasses:
  - squad-note
tags:
  - squad
  - software-dev
  - security
  - pentesting
  - incident-response
---

# 🛡️ Cybersecurity-Squad — Security Specialists

> *"A segurança não é um produto. É um processo — e começa antes do ataque."*

Squad especialista em segurança que entra quando o projeto lida com dados sensíveis, smart contracts, infraestrutura crítica ou precisa de security review rigoroso. Potencializa [[Neo — Dev]] e [[Operator — DevOps]] com perspectiva de segurança em todas as camadas.

## Agentes Especializados
| Persona | Especialidade | Comando Chave |
|---------|--------------|---------------|
| **Pentester** | Testes de penetração, vulnerability assessment, red team | `*pentest {target}` |
| **Security Architect** | Threat modeling, security by design, ZeroTrust | `*threat-model {sistema}` |
| **Incident Responder** | IR playbooks, forense digital, recovery | `*ir-playbook {cenário}` |

## Quando Usar
- Projeto com dados sensíveis (PII, financeiros, saúde)
- Smart contracts e Web3 (rug-pull vectors, reentrancy, etc.)
- VPS/infra hardening (como o Smith INFECTED→CLEAN do projeto)
- Auditoria de segurança antes de lançamento
- Resposta a incidente de segurança

## Áreas de Cobertura
| Área | Especialista |
|------|-------------|
| Web App Security (OWASP Top 10) | Pentester |
| Smart Contract Security | Pentester + Security Architect |
| Cloud/VPS Hardening | Security Architect |
| Zero Trust Architecture | Security Architect |
| Incident Response | Incident Responder |

## Workflows Enhanced
Potencializa [[Neo — Dev]] (code security review) e [[Operator — DevOps]] (infra hardening). Complementa [[Smith — Delivery Verifier]] em projetos de alta criticidade.

## Ativação
`*discover security` via [[Morpheus — LMAS Master]] ou acionado automaticamente em projetos Web3/DeFi.

## Arquivo Fonte
`squads/cybersecurity-squad/squad.yaml`
