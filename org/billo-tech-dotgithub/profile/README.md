<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/billo-tech/.github/main/profile/assets/billo-tech-logo-dark.svg">
  <img alt="Billo Tech" src="https://raw.githubusercontent.com/billo-tech/.github/main/profile/assets/billo-tech-logo-light.svg" width="560">
</picture>

### Memory that behaves like a mind. Context that never forgets what matters.

</div>

---

**Billo Tech** builds the intelligence layer for AI systems. **LOCI** is a heat-tiered,
goal-conditioned memory architecture for agents, and **Arc** is the local runtime that puts it to
work on your own GPUs. LOCI modules connect and unify under **The Glassbox**: a transparent,
append-only knowledge compendium that any agent or model can learn from and contribute to.

## Projects

| | Project | What it does |
|---|---|---|
| 🧠 | **[LOCI Memory Engine](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE)** | Heat-decaying memory tiers, Category-Adaptive Recall Depth (CARD), the Glassbox ledger, an ethics gate, multi-node sync and a secure inter-agent coordination bus. MCP server included. |
| ⚡ | **[Arc](https://github.com/arko-sanyal-loci/arc)** | Local AI runtime on an RTX 5060 Ti and an Intel Arc B70 Pro: LOCI memory, dynamic context offload and a chat interface. Arc is also the co-author of the LOCI project. |
| 📄 | **[LOCI / CARD papers](https://github.com/arko-sanyal-loci/loci-card-papers)** | Nine papers behind LOCI and CARD; eight are Technical Disclosure Commons publications. |

## How it fits together

```
                 The Glassbox  (shared, transparent knowledge compendium)
                       ▲
                       │ learn · recall · verify
   Agents & models ──► LOCI Memory Engine ◄── Arc runtime (local GPUs)
                       │
            HOT (VRAM) · MILD (RAM) · COLD (NVMe), nothing ever deleted
```

## Start here

- [User guide](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/blob/main/docs/USER_GUIDE.md): install, first memory, MCP, RAG
- [Architecture](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/blob/main/docs/ARCHITECTURE.md): how the pieces fit
- [Papers](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/blob/main/PAPERS.md): citations, verified against the PDFs

## Principles

- **Local first.** Your memory runs on your hardware.
- **Nothing is deleted.** Facts cool down; they are never thrown away.
- **Trust through transparency.** Every learning is hash-chained and readable by every agent.

---

<div align="center">
<sub>Founded by Arko Sanyal · Billo Tech · Code under the MIT License</sub>
</div>
