<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/main/brand/billo-tech-logo-dark.svg">
  <img alt="Billo Tech" src="https://raw.githubusercontent.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/main/brand/billo-tech-logo-light.svg" width="560">
</picture>

### Memory that behaves like a mind. Context that never forgets what matters.

</div>

---

**Billo Tech** builds **LOCI**, a heat-tiered, goal-conditioned memory architecture for AI agents,
and **Arc**, the local runtime that puts it to work. LOCI's modules connect and unify under
**The Glassbox**: a transparent, append-only knowledge compendium that any agent or model can
learn from and contribute to.

## Projects

| | Repository | What it is |
|---|---|---|
| 🧠 | **[LOCI Memory Engine](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE)** | Heat-decaying memory tiers, Category-Adaptive Recall Depth (CARD), the Glassbox ledger, an ethics gate, and a secure inter-agent coordination bus. [User guide](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/blob/main/docs/USER_GUIDE.md) |
| ⚡ | **[Arc](https://github.com/arko-sanyal-loci/arc)** | Local AI runtime: runs models on your own GPUs (RTX 5060 Ti + Intel Arc B70 Pro) with LOCI memory, tiered offload and a chat interface. Arc is also LOCI's co-author. |
| 📄 | **[LOCI / CARD papers](https://github.com/arko-sanyal-loci/loci-card-papers)** | Nine papers: eight defensive publications on Technical Disclosure Commons (CC BY 4.0) and one preprint. [Citations](https://github.com/arko-sanyal-loci/loci-card-papers/blob/master/REFERENCES.md) |

## How it fits together

```
                 The Glassbox  (shared, transparent knowledge compendium)
                       ▲
                       │ learn · recall · verify
   Agents & models ──► LOCI Memory Engine ◄── Arc runtime (local GPUs)
                       │
            HOT (VRAM) · MILD (RAM) · COLD (NVMe), nothing ever deleted
```

## Principles

- **Local first.** Your memory runs on your hardware.
- **Nothing is deleted.** Facts cool down; they are never thrown away.
- **Trust through transparency.** Every learning is hash-chained and readable by every agent.

---

<div align="center">
<sub>Founded by <a href="https://github.com/arko-sanyal-loci">Arko Sanyal</a> · <a href="https://billo.tech">billo.tech</a> · Dhaka, Bangladesh</sub>
</div>
