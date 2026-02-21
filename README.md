# 🐜 Ant v0.3.0

**High-ratio lossless compressor + Agent Mode** that saves **70–90% tokens** when feeding repos to AI coding tools.

[GitHub Repository](https://github.com/Okediya/antcompress)

```bash
pip install antcompress[agent]
```

## Commands
- `ant compress <path>` → tiny .ant file (95–99% smaller)
- `ant decompress <file.ant>` → restore exact original
- `ant pack-ai <folder>` → Agent Mode (JSON for IDEs or MD for phone)
- `ant unpack-ai <edited.md>` → AI changes → new .ant

## Quick Start
```bash
ant pack-ai . --stdout --model claude
```

## Phone Workflow (no Termux)
1. `ant pack-ai my-repo/`
2. Send `my-repo.ai.md` to phone.
3. Paste into Claude/Grok/ChatGPT.
4. Save AI reply as `edited.md`.
5. Send back → `ant unpack-ai edited.md` → `ant decompress updated.ant`

## Agent Mode in IDEs

### Cursor / Continue.dev
Add to `~/.continue/config.json`:
```json
"context": [{
  "provider": "command",
  "params": {
    "command": "ant pack-ai . --format json --model claude --max-tokens 120000 --stdout",
    "name": "ant-repo"
  }
}]
```
Type `@ant-repo` in chat.

### Aider
```bash
aider --context-cmd "ant pack-ai . --format json --model claude --max-tokens 128000 --stdout"
```

### GitHub Copilot
Run `ant pack-ai . --stdout` and paste the output into Copilot Chat to give it full project context while staying under the token limit.

### Google Antigravity
Since Antigravity can use your terminal, simply ask it to:
*"Use Ant to pack this repo for context"* or *"Use Ant to apply changes from this edited.md file."*

---
Made with ❤️ by Okediya Ayobami Oluwaseunfunmi