## Engineering Workflow

For substantial software engineering tasks:

- Use spec-driven development when requirements are ambiguous or a feature spans multiple modules.
- Use test-driven development when adding behavior or fixing reproducible bugs, where practical.
- Use code review and quality checks before declaring implementation complete.
- Use incremental implementation for complex changes; validate each meaningful step.
- Use codebase-memory-mcp when architectural discovery, call-chain analysis, or cross-file impact analysis is relevant.
- Apply Anti-Slop principles to avoid generic UI, unnecessary abstractions, filler content, and unverified claims.
- Use Taste Skill when designing or improving frontend interfaces.
- Prefer the installed skill's documented workflow when it matches the task. Do not force irrelevant skills into trivial requests.
- Verify changes with relevant tests, inspect the diff, and report what was actually validated.


## Browser Automation — agent-browser

When a task requires real browser interaction, use `agent-browser` instead of relying solely on assumptions about website behavior.

Use it when:
- Testing a locally running web application.
- Verifying UI changes and user flows.
- Navigating websites, interacting with forms, or extracting visible page information.
- Performing exploratory testing and reproducing browser-related bugs.

Workflow:
1. Check `agent-browser --help` if command syntax is unclear.
2. Load the current workflow using `agent-browser skills get core`.
3. Navigate using `agent-browser open <url>`.
4. Inspect interactive elements using `agent-browser snapshot -i`.
5. Interact using the returned element references, then take a fresh snapshot after page changes.
6. Verify the actual result rather than assuming an action succeeded.

Use specialized skills when relevant, such as `dogfood` for exploratory testing or `electron` for supported Electron applications.

Do not launch browser automation for unrelated tasks. Ask for authorization before performing consequential actions such as submitting transactions, publishing content, deleting data, or changing account settings.

### UI Icon Guidelines

- Gunakan Lucide sebagai library ikon utama untuk antarmuka web.
- Untuk React, gunakan package `lucide-react`.
- Pilih ikon berdasarkan makna dan konteks UI.
- Hindari emoji sebagai pengganti ikon UI profesional.
- Jangan membuat SVG ikon sendiri jika ikon yang sesuai sudah tersedia di Lucide.
- Gunakan ukuran, warna, dan stroke yang konsisten dengan desain.
- Import hanya ikon yang diperlukan.
- Periksa framework dan package yang sudah digunakan sebelum memasang dependency baru.

### GSAP Animation Guidelines

- Pertimbangkan GSAP untuk animasi kompleks, timeline berurutan, stagger, scroll-triggered animation, SVG, dan transisi yang membutuhkan kontrol presisi.
- Sebelum implementasi, periksa framework dan dependency project.
- Jika GSAP diperlukan tetapi belum terpasang, pasang dependency di project menggunakan package manager yang sesuai.
- Gunakan dokumentasi dan skill resmi GSAP untuk memilih API dan plugin yang tepat.
- Untuk React, pastikan animasi dibersihkan dengan benar saat komponen dilepas; pertimbangkan `@gsap/react` dan `useGSAP()`.
- Untuk animasi sederhana seperti hover atau perubahan warna, prioritaskan CSS jika sudah memadai.
- Hormati `prefers-reduced-motion` dan hindari animasi yang mengganggu aksesibilitas atau performa.
- Jangan memasang GSAP atau plugin tambahan jika tidak dibutuhkan oleh implementasi.