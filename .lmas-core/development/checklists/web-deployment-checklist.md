# Web Deployment Checklist

Checklist obrigatório para qualquer story que envolve deploy de site, landing page, ou feature web pública.

**Quando usar:** Antes de considerar "Done" qualquer implementação web acessada por usuários finais.
**Quem executa:** @dev (implementa) → @qa (valida) → @devops (deploya)

---

## 1. Metadata & SEO

- [ ] `<title>` definido e descritivo (50-60 chars)
- [ ] `<meta name="description">` definido (150-160 chars)
- [ ] `<meta name="viewport">` presente
- [ ] `<html lang="pt-BR">` (ou idioma correto)
- [ ] Canonical URL definida
- [ ] Heading hierarchy correta (H1 único por página)

## 2. OpenGraph (Compartilhamento Social)

- [ ] `og:title` definido
- [ ] `og:description` definido
- [ ] `og:image` definido (1200x630px recomendado)
- [ ] `og:url` definido
- [ ] `og:type` definido (website, article, etc.)
- [ ] `og:site_name` definido
- [ ] `og:locale` definido (pt_BR)
- [ ] **opengraph-image** gerado (Next.js: app/opengraph-image.tsx ou arquivo estático)
- [ ] Testado em debugger de OpenGraph

## 3. Twitter Card

- [ ] `twitter:card` definido (summary_large_image)
- [ ] `twitter:title` definido
- [ ] `twitter:description` definido
- [ ] `twitter:image` definido

## 4. Favicon & Icons

- [ ] `favicon.ico` na raiz (32x32 ou multi-size)
- [ ] `apple-touch-icon.png` (180x180)
- [ ] Favicon visível na tab do browser

## 5. Arquivos Estáticos Essenciais

- [ ] `robots.txt` na raiz
- [ ] `sitemap.xml` gerado
- [ ] `manifest.json` / `site.webmanifest` (para PWA/mobile)

## 6. Performance & Core Web Vitals

- [ ] Imagens otimizadas (WebP/AVIF, lazy loading)
- [ ] Fonts otimizadas (preload, font-display: swap)
- [ ] LCP < 2.5s, FID < 100ms, CLS < 0.1

## 7. Segurança

- [ ] HTTPS ativo
- [ ] Sem secrets/API keys expostos no client-side
- [ ] rel="noopener noreferrer" em links externos target="_blank"

## 8. Acessibilidade (Mínimo)

- [ ] Imagens têm alt text
- [ ] Contraste WCAG AA (4.5:1)
- [ ] Formulários têm labels
- [ ] Navegação funciona via teclado

## 9. Analytics & Tracking

- [ ] Analytics configurado
- [ ] Eventos de conversão (se aplicável)
- [ ] Consent banner LGPD/GDPR (se necessário)

## 10. Deploy & DNS

- [ ] Domínio apontando corretamente
- [ ] WWW redirect configurado
- [ ] 404 page customizada
- [ ] Build de produção sem erros

---

## Integração com LMAS

Este checklist é acionado quando:
- Story envolve landing page, site, deploy web, ou página pública
- @dev marca story como Ready for Review
- @qa inclui na quality gate
- @seo (Cypher) valida itens 1-3 via *audit
- @smith verifica como parte do adversarial review
