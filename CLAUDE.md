# Project: lead generation for a Peru web agency (dental clinics, Lima)

Start by reading `agencia-web-peru/RESUME.md`: it has the decisions, the file map, the data status and the next steps.

Working rules:
- The user wants things done autonomously and without questions; make sensible defaults and report briefly.
- Messages to clinics are sent by the user (pre-filled `wa.me` links, or the local bridge + Claude Desktop with per-send approval, see `agencia-web-peru/WHATSAPP_DESKTOP.md`). Never unattended, never from the cloud. Prefer inbound channels.
- Lead data lives in `agencia-web-peru/leads/data/` and is git-ignored here (this repo is PUBLIC; never commit it). The private copy is the repo `AlanPerezD/agencia-web-peru-leads` (folder `data/`).
- Apify MCP (`mcp__Apify__*`) is connected; stay within the free monthly credit (see `agencia-web-peru/leads/APIFY_QUICKSTART.md`).
- Run tests with `cd agencia-web-peru/leads && python3 -m unittest test_leads`.
