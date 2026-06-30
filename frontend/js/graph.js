/**
 * WikiKnowledge — D3.js Knowledge Graph Visualization
 */

const Graph = {
    _simulation: null,
    _svg: null,
    _g: null,
    _zoom: null,
    _width: 0,
    _height: 0,

    /**
     * Initialize the graph view with full graph data.
     */
    async init() {
        const container = document.getElementById('graph-container');
        const svgEl = document.getElementById('graph-svg');

        this._width = container.clientWidth;
        this._height = container.clientHeight;

        // Clear previous
        d3.select(svgEl).selectAll('*').remove();
        if (this._simulation) this._simulation.stop();

        this._svg = d3.select(svgEl)
            .attr('width', this._width)
            .attr('height', this._height);

        // Background gradient
        const defs = this._svg.append('defs');
        const gradient = defs.append('radialGradient')
            .attr('id', 'bg-gradient')
            .attr('cx', '50%').attr('cy', '50%').attr('r', '50%');
        gradient.append('stop').attr('offset', '0%').attr('stop-color', 'var(--bg-tertiary)');
        gradient.append('stop').attr('offset', '100%').attr('stop-color', 'var(--bg-primary)');

        this._svg.append('rect')
            .attr('width', this._width)
            .attr('height', this._height)
            .attr('fill', 'url(#bg-gradient)');

        // Arrow marker for directed links
        defs.append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#4a5568');

        // Zoom layer
        this._g = this._svg.append('g');
        this._zoom = d3.zoom()
            .scaleExtent([0.1, 5])
            .on('zoom', (event) => {
                this._g.attr('transform', event.transform);
            });
        this._svg.call(this._zoom);

        // Fetch and render
        try {
            const data = await API.fetchGraph();
            this._renderGraph(data);
        } catch (e) {
            console.error('Failed to load graph:', e);
        }

        // Reset button
        document.getElementById('btn-graph-reset').onclick = () => {
            this._svg.transition().duration(500)
                .call(this._zoom.transform, d3.zoomIdentity);
        };
    },

    _renderGraph(data) {
        if (!data.nodes.length) return;

        const { nodes, links } = data;

        // Color scale
        const colorMap = {
            leaf: '#3b82f6',
            category: '#a855f7',
            resource: '#14b8a6',
        };

        // Size scale based on link count
        const maxLinks = Math.max(...nodes.map(n => n.linkCount), 1);
        const sizeScale = d3.scaleSqrt().domain([0, maxLinks]).range([5, 18]);

        // Force simulation
        this._simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter(this._width / 2, this._height / 2))
            .force('collision', d3.forceCollide().radius(d => sizeScale(d.linkCount) + 10));

        // Links
        const link = this._g.append('g')
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('class', 'graph-link')
            .attr('stroke-width', 1)
            .attr('marker-end', 'url(#arrowhead)');

        // Nodes group
        const node = this._g.append('g')
            .selectAll('g')
            .data(nodes)
            .join('g')
            .attr('class', 'graph-node')
            .call(this._drag(this._simulation));

        // Node shapes: circles for articles, diamonds for resources
        node.each(function (d) {
            const el = d3.select(this);
            const r = sizeScale(d.linkCount);
            const color = colorMap[d.type] || '#6366f1';

            if (d.type === 'resource') {
                // Diamond shape for resources
                el.append('polygon')
                    .attr('points', `0,${-r} ${r},0 0,${r} ${-r},0`)
                    .attr('fill', color)
                    .attr('stroke', d3.color(color).brighter(0.5))
                    .attr('stroke-width', 1.5)
                    .attr('opacity', 0.85)
                    .attr('class', 'node-shape');
            } else {
                // Circle for articles
                el.append('circle')
                    .attr('r', r)
                    .attr('fill', color)
                    .attr('stroke', d3.color(color).brighter(0.5))
                    .attr('stroke-width', 1.5)
                    .attr('opacity', 0.85)
                    .attr('class', 'node-shape');
            }
        });

        // Node glow effect
        node.each(function (d) {
            const el = d3.select(this);
            const r = sizeScale(d.linkCount) + 4;
            const color = colorMap[d.type] || '#6366f1';

            if (d.type === 'resource') {
                el.append('polygon')
                    .attr('points', `0,${-r} ${r},0 0,${r} ${-r},0`)
                    .attr('fill', 'none')
                    .attr('stroke', color)
                    .attr('stroke-width', 0.5)
                    .attr('opacity', 0.3);
            } else {
                el.append('circle')
                    .attr('r', r)
                    .attr('fill', 'none')
                    .attr('stroke', color)
                    .attr('stroke-width', 0.5)
                    .attr('opacity', 0.3);
            }
        });

        // Labels
        node.append('text')
            .attr('class', 'graph-node-label')
            .attr('dy', d => sizeScale(d.linkCount) + 14)
            .text(d => d.title.length > 20 ? d.title.substring(0, 18) + '…' : d.title);

        // Tooltip
        const tooltip = document.getElementById('graph-tooltip');

        node.on('mouseover', (event, d) => {
            const typeInfo = d.type === 'resource' ? `resource (${d.mime_type || 'unknown'})` : d.type;
            tooltip.innerHTML = `
                <div class="tooltip-title">${Utils.escapeHtml(d.title)}</div>
                <div class="tooltip-type">${typeInfo} · ${d.linkCount} connections</div>
                ${d.tags && d.tags.length ? `<div style="margin-top:4px;font-size:11px;color:var(--text-muted);">Tags: ${d.tags.join(', ')}</div>` : ''}
            `;
            tooltip.style.left = `${event.pageX + 15}px`;
            tooltip.style.top = `${event.pageY - 10}px`;
            tooltip.classList.remove('hidden');

            // Highlight connected
            const connectedIds = new Set();
            links.forEach(l => {
                const sId = typeof l.source === 'object' ? l.source.id : l.source;
                const tId = typeof l.target === 'object' ? l.target.id : l.target;
                if (sId === d.id) connectedIds.add(tId);
                if (tId === d.id) connectedIds.add(sId);
            });

            node.select('.node-shape')
                .attr('opacity', n => n.id === d.id || connectedIds.has(n.id) ? 1 : 0.2);

            link.attr('stroke-opacity', l => {
                const sId = typeof l.source === 'object' ? l.source.id : l.source;
                const tId = typeof l.target === 'object' ? l.target.id : l.target;
                return sId === d.id || tId === d.id ? 0.8 : 0.1;
            });
        });

        node.on('mouseout', () => {
            tooltip.classList.add('hidden');
            node.select('.node-shape').attr('opacity', 0.85);
            link.attr('stroke-opacity', 0.4);
        });

        // Click to navigate
        node.on('click', (event, d) => {
            window.location.hash = `#/article/${d.id}`;
        });

        // Tick
        this._simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
    },

    _drag(simulation) {
        return d3.drag()
            .on('start', (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    },

    /**
     * Reset/recenter the graph view.
     */
    resetView() {
        if (this._svg && this._zoom) {
            this._svg.transition().duration(500)
                .call(this._zoom.transform, d3.zoomIdentity);
        }
    },
};
