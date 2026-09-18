/**
 * WikiKnowledge — D3.js Knowledge Graph Visualization
 * 
 * D3.js force-directed graph rendering.
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

        // Arrow markers for directed links
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
            .attr('fill', '#64748b');

        // Arrow marker for leaf-to-category directed links (bright purple)
        defs.append('marker')
            .attr('id', 'arrowhead-category')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#a855f7');

        // Arrow marker for resource links
        defs.append('marker')
            .attr('id', 'arrowhead-resource')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#14b8a6');

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

        // Quick lookup map for nodes by id
        const nodeMap = new Map(nodes.map(n => [n.id, n]));
        const getNode = (ref) => {
            if (!ref) return null;
            if (typeof ref === 'object') return ref;
            return nodeMap.get(ref);
        };

        const isCategoryLink = (l) => {
            const s = getNode(l.source);
            const t = getNode(l.target);
            if (!s || !t) return false;

            // 1. Leaf to category (or category to leaf)
            if ((s.type === 'leaf' && (t.type === 'category' || (Array.isArray(s.categories) && s.categories.includes(t.id)))) ||
                (t.type === 'leaf' && (s.type === 'category' || (Array.isArray(t.categories) && t.categories.includes(s.id))))) {
                return true;
            }

            // 2. Category to parent category (category to category)
            if (s.type === 'category' && t.type === 'category') {
                return true;
            }

            // 3. Category membership via categories array
            if ((Array.isArray(s.categories) && s.categories.includes(t.id)) ||
                (Array.isArray(t.categories) && t.categories.includes(s.id))) {
                return true;
            }

            return false;
        };
        const isLeafToCategory = isCategoryLink;

        const isResourceLink = (l) => {
            const s = getNode(l.source);
            const t = getNode(l.target);
            if (!s || !t) return false;
            return s.type === 'resource' || t.type === 'resource';
        };

        const getLinkClass = (l) => {
            if (isLeafToCategory(l)) return 'graph-link graph-link-category';
            if (isResourceLink(l)) return 'graph-link graph-link-resource';
            return 'graph-link graph-link-article';
        };

        const getLinkMarker = (l) => {
            if (isLeafToCategory(l)) return 'url(#arrowhead-category)';
            if (isResourceLink(l)) return 'url(#arrowhead-resource)';
            return 'url(#arrowhead)';
        };

        const getLinkDefaultOpacity = (l) => {
            if (isLeafToCategory(l)) return 0.75;
            if (isResourceLink(l)) return 0.45;
            return 0.25; // article-to-article is dimmer
        };

        const getLinkColor = (l) => {
            if (isLeafToCategory(l)) return '#a855f7';
            if (isResourceLink(l)) return '#14b8a6';
            return '#64748b';
        };

        const getLinkStrokeWidth = (l) => {
            if (isLeafToCategory(l)) return 1.5;
            return 1;
        };

        // Render category links after article links so bright category links sit on top
        links.sort((a, b) => {
            const aCat = isLeafToCategory(a) ? 1 : 0;
            const bCat = isLeafToCategory(b) ? 1 : 0;
            return aCat - bCat;
        });

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
            .attr('class', l => getLinkClass(l))
            .attr('stroke', l => getLinkColor(l))
            .attr('stroke-width', l => getLinkStrokeWidth(l))
            .attr('stroke-opacity', l => getLinkDefaultOpacity(l))
            .attr('marker-end', l => getLinkMarker(l));

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
            .text(d => {
                let text = d.title.length > 20 ? d.title.substring(0, 18) + '…' : d.title;
                const sourcesList = (window.App && window.App._sources) ? window.App._sources : [];
                const sourceInfo = Utils.getSourceInfo(d, sourcesList);
                if (sourceInfo.type !== 'native') {
                    text = sourceInfo.icon + ' ' + text;
                }
                return text;
            });

        // Tooltip
        const tooltip = document.getElementById('graph-tooltip');

        node.on('mouseover', (event, d) => {
            const sourcesList = (window.App && window.App._sources) ? window.App._sources : [];
            const sourceInfo = Utils.getSourceInfo(d, sourcesList);

            let typeInfo = d.type === 'resource' ? `resource (${d.mime_type || 'unknown'})` : (sourceInfo.type !== 'native' ? sourceInfo.label : d.type);
            const icon = sourceInfo.type !== 'native' ? sourceInfo.icon + ' ' : '';
            const tagList = d.tags && d.tags.length ? d.tags.map(t => `#${t}`).join(' ') : '';
            
            tooltip.innerHTML = `
                <div class="tooltip-title">${icon + Utils.escapeHtml(d.title)}</div>
                <div class="tooltip-type">${Utils.escapeHtml(typeInfo)} · ${d.linkCount} connections</div>
                ${tagList ? `<div style="margin-top:4px;font-size:11px;color:var(--text-muted);">${Utils.escapeHtml(tagList)}</div>` : ''}
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

            link
                .classed('highlighted', l => {
                    const sId = typeof l.source === 'object' ? l.source.id : l.source;
                    const tId = typeof l.target === 'object' ? l.target.id : l.target;
                    return sId === d.id || tId === d.id;
                })
                .attr('stroke', l => {
                    const sId = typeof l.source === 'object' ? l.source.id : l.source;
                    const tId = typeof l.target === 'object' ? l.target.id : l.target;
                    const isConnected = sId === d.id || tId === d.id;
                    if (isConnected) {
                        return isLeafToCategory(l) ? '#c084fc' : (isResourceLink(l) ? '#2dd4bf' : '#94a3b8');
                    }
                    return getLinkColor(l);
                })
                .attr('stroke-width', l => {
                    const sId = typeof l.source === 'object' ? l.source.id : l.source;
                    const tId = typeof l.target === 'object' ? l.target.id : l.target;
                    const isConnected = sId === d.id || tId === d.id;
                    if (isConnected) {
                        return isLeafToCategory(l) ? 2 : 1.5;
                    }
                    return getLinkStrokeWidth(l);
                })
                .attr('stroke-opacity', l => {
                    const sId = typeof l.source === 'object' ? l.source.id : l.source;
                    const tId = typeof l.target === 'object' ? l.target.id : l.target;
                    const isConnected = sId === d.id || tId === d.id;
                    if (!isConnected) return 0.08;
                    return isLeafToCategory(l) ? 0.95 : 0.75;
                });
        });

        node.on('mouseout', () => {
            tooltip.classList.add('hidden');
            node.select('.node-shape').attr('opacity', 0.85);
            link
                .classed('highlighted', false)
                .attr('stroke', l => getLinkColor(l))
                .attr('stroke-width', l => getLinkStrokeWidth(l))
                .attr('stroke-opacity', l => getLinkDefaultOpacity(l));
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
