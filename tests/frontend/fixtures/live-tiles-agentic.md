# Live Tiles as Autonomous Agent Surfaces

## The Evolution of the Application Icon
In FluentOS, applications are not static silos; they are **autonomous background agents running in [[vm-agent-workers|VMs]]**. Consequently, FluentOS evolves the iconic Windows Phone 8 **Live Tile** into an **Agent Telemetry Surface**.

```mermaid
flowchart LR
    Agent["<b>Autonomous Agent Scout (in VM)</b><br/>• Indexes 84 code repositories<br/>• Detects 3 architectural synergies"]
    
    subgraph Tile ["3D Flipping Live Tile (Surface Layer)"]
        Front["<b>Front Side: Real-Time Status</b><br/>'Indexed 84 Code Repos'<br/>Status: Healthy (Green LED)"]
        Back["<b>Back Side: Deep Reasoning Trace</b><br/>'Identified Metro Panorama reduces<br/>navigational fatigue by 42%'<br/>[Inspect Reasoning Tree →]"]
    end

    Agent -->|Pushes State Delta| Front
    Front <-->|3D Y-Axis Flip (Periodic or Tap)| Back
```

---

## 1. Dimensionality & Form Factors
* **Small Tile ($1\times 1$):** Used for single key performance indicators.
* **Medium Tile ($2\times 2$):** Used for single-agent status.

### A. The 3D Flip Mechanic (Front $\leftrightarrow$ Back)
* **Back Face:** Flips $180^\circ$ along the Y-axis to reveal the agent's internal reasoning trace.

### B. The Authentic 3D Tilt Effect
When a user presses down on a tile (or moves their pointer over it), the tile does not merely dim; it **tilts into the 3D plane**:
$$\text{transform: } \text{scale}(0.97) \,\, \text{perspective}(600\text{px}) \,\, \text{rotateX}(4^\circ)$$
This micro-interaction originated in Windows Phone 7/8.

See also: [[panorama-pattern]], [[vm-agent-workers]].
