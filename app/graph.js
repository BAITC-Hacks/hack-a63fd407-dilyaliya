/* Canvas rendering and camera only. No role or ranking calculations. */
'use strict';
const GraphUI = (() => {
  const roles = {
    coordinator: {label: 'Координация', color: '#bc9cff', shape: 'diamond', icon: '◆'},
    consolidator: {label: 'Сбор средств', color: '#ff83b5', shape: 'square', icon: '■'},
    distributor: {label: 'Распределение', color: '#ffd070', shape: 'triangle', icon: '▲'},
    transit: {label: 'Транзит', color: '#7cafff', shape: 'circle', icon: '●'},
    terminal: {label: 'Получатель', color: '#53dfc6', shape: 'hexagon', icon: '⬢'},
    peripheral: {label: 'Периферия', color: '#8396b5', shape: 'cross', icon: '+'}
  };
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const limits = {min: .015, max: 8};
  const edgeKey = e => `${e.src}>${e.dst}`;

  function zoomCamera(camera, factor, anchor, destination = anchor) {
    const scale = clamp(camera.scale * factor, limits.min, limits.max);
    return {
      scale,
      x: destination.x - (anchor.x - camera.x) * scale / camera.scale,
      y: destination.y - (anchor.y - camera.y) * scale / camera.scale
    };
  }

  function fitCamera(points, width, height, center = null) {
    if (!points.length) return {scale: 1, x: width / 2, y: height / 2};
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const cx = center ? center.x : (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = center ? center.y : (Math.min(...ys) + Math.max(...ys)) / 2;
    const spanX = 2 * Math.max(...xs.map(x => Math.abs(x - cx))) + 70;
    const spanY = 2 * Math.max(...ys.map(y => Math.abs(y - cy))) + 70;
    const scale = clamp(Math.min(Math.max(20, width - 40) / spanX,
                                 Math.max(20, height - 60) / spanY, 3), limits.min, limits.max);
    return {scale, x: width / 2 - cx * scale, y: height / 2 - cy * scale};
  }

  function edgeWidths(amounts) {
    const sorted = [...amounts].sort((a, b) => a - b);
    const cap = sorted[Math.max(0, Math.ceil(sorted.length * .95) - 1)] || 1;
    return {cap, width: amount => clamp(.6 + 2.2 * amount / cap, .6, 2.8)};
  }

  function nodeCamera(node, nearby, width, height) {
    // A distant counterparty must not turn a node selection into a zoom-out.
    // The explicit Fit action still fits every direct counterparty.
    const fitted = fitCamera(nearby, width, height, node);
    const scale = clamp(fitted.scale, .5, 1.8);
    return {scale, x: width / 2 - node.x * scale, y: height / 2 - node.y * scale};
  }

  function pairGeometry(points) {
    const [a, b] = [...points.values()];
    return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2,
            distance: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y))};
  }

  /* Pure pointer state: testable without a browser, including pinch cancellation. */
  class Gesture {
    constructor() { this.points = new Map(); this.moved = false; }
    down(id, point) {
      if (!this.points.size) this.moved = false;
      this.points.set(id, {...point, startX: point.x, startY: point.y});
      if (this.points.size > 1) this.moved = true;
    }
    move(id, point, camera) {
      const old = this.points.get(id);
      if (!old) return camera;
      const before = this.points.size >= 2 ? pairGeometry(this.points) : null;
      this.points.set(id, {...old, ...point});
      if (Math.hypot(point.x - old.startX, point.y - old.startY) > 4) this.moved = true;
      if (before) {
        const after = pairGeometry(this.points);
        return zoomCamera(camera, after.distance / before.distance, before, after);
      }
      return {...camera, x: camera.x + point.x - old.x, y: camera.y + point.y - old.y};
    }
    up(id, cancelled = false) {
      const known = this.points.has(id);
      const click = known && this.points.size === 1 && !this.moved && !cancelled;
      this.points.delete(id);
      if (cancelled) this.moved = true;
      return click;
    }
  }

  class GraphView {
    constructor(canvas, dataset, callbacks) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.nodeSprites = this.createNodeSprites();
      this.nodes = dataset.nodes;
      this.map = new Map(this.nodes.map(n => [n.gid, n]));
      this.callbacks = callbacks;
      this.camera = {scale: 1, x: 0, y: 0};
      this.baseScale = 1;
      this.width = 1;
      this.height = 1;
      this.ready = false;
      this.selected = null;
      this.cluster = null;
      this.mode = 'all';
      this.enabled = new Set(Object.keys(roles));
      this.gesture = new Gesture();
      this.adjacent = new Map(this.nodes.map(n => [n.gid, new Set([n.gid])]));
      this.weightScale = edgeWidths(dataset.edges.map(e => e.sum_kzt));
      this.edges = dataset.edges.map(e => {
        this.adjacent.get(e.src).add(e.dst);
        this.adjacent.get(e.dst).add(e.src);
        return {...e, a: this.map.get(e.src), b: this.map.get(e.dst), stroke: this.weightScale.width(e.sum_kzt)};
      });
      this.groups = new Map();
      for (const n of this.nodes) {
        if (!this.groups.has(n.cluster_id)) this.groups.set(n.cluster_id, []);
        this.groups.get(n.cluster_id).push(n);
      }
      this.hulls = [...this.groups].map(([id, nodes]) => {
        const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
        return {id, count: nodes.length, left: Math.min(...xs) - 19, right: Math.max(...xs) + 19,
                top: Math.min(...ys) - 19, bottom: Math.max(...ys) + 19};
      });
      this.rebuild();
      this.bindEvents();
      this.observer = new ResizeObserver(() => this.resize());
      this.observer.observe(canvas.parentElement);
    }

    point(n) {
      return this.mode === 'path' && this.pathOrder.has(n.gid)
        ? {x: 0, y: this.pathOrder.get(n.gid) * 120} : n;
    }

    screen(n) {
      const p = this.point(n), c = this.camera;
      return {x: p.x * c.scale + c.x, y: p.y * c.scale + c.y};
    }

    radius(n) {
      const size = (3 + 4 * n.priority_score) * Math.sqrt(this.camera.scale);
      return clamp(size * (n.role === 'peripheral' ? .65 : 1), n.role === 'peripheral' ? 1.3 : 2, 12);
    }

    rebuild() {
      const path = this.map.get(this.selected)?.seed_path || [];
      this.pathOrder = new Map(path.map((id, i) => [id, i]));
      this.pathEdges = new Set(path.slice(1).map((gid, i) => `${path[i]}>${gid}`));
      const ego = this.adjacent.get(this.selected) || new Set();
      this.visible = this.nodes.filter(n => this.enabled.has(n.role)
        && (this.mode !== 'ego' || ego.has(n.gid))
        && (this.mode !== 'path' || this.pathOrder.has(n.gid)));
      this.ids = new Set(this.visible.map(n => n.gid));
      this.related = this.selected ? ego : new Set(this.visible.filter(n => n.cluster_id === this.cluster).map(n => n.gid));
      const shown = this.edges.filter(e => this.ids.has(e.src) && this.ids.has(e.dst)
        && (this.mode !== 'path' || this.pathEdges.has(edgeKey(e))));
      this.links = [shown.filter(e => !this.activeEdge(e)), shown.filter(e => this.activeEdge(e))];
      this.visibleGroups = new Set(this.visible.map(n => n.cluster_id));
      this.callbacks.state?.({nodes: this.visible.length, edges: shown.length});
      this.invalidate();
    }

    activeEdge(e) {
      return this.selected ? e.src === this.selected || e.dst === this.selected
        : this.cluster !== null && e.a.cluster_id === this.cluster && e.b.cluster_id === this.cluster;
    }

    select(gid) {
      this.selected = gid;
      this.cluster = null;
      this.rebuild();
      if (this.mode === 'all') {
        const node = this.map.get(gid);
        const nearby = this.visible.filter(n => n.cluster_id === node.cluster_id && this.related.has(n.gid));
        this.camera = nodeCamera(node, nearby, this.width, this.height);
        this.invalidate();
      } else this.focus();
    }

    selectCluster(id) {
      this.selected = null;
      this.cluster = id;
      this.mode = 'all';
      this.rebuild();
      this.focus();
    }

    setRoles(enabled) { this.enabled = new Set(enabled); this.rebuild(); }
    setMode(mode) { this.mode = this.selected ? mode : 'all'; this.rebuild(); this.focus(); }

    focus() {
      let nodes = this.visible, center = null;
      if (this.mode === 'all' && this.selected) {
        nodes = this.visible.filter(n => this.adjacent.get(this.selected).has(n.gid));
        center = this.map.get(this.selected);
      } else if (this.cluster !== null) {
        nodes = this.visible.filter(n => n.cluster_id === this.cluster);
      }
      if (nodes.length) this.camera = fitCamera(nodes.map(n => this.point(n)), this.width, this.height, center);
      this.invalidate();
    }

    reset() {
      this.selected = null;
      this.cluster = null;
      this.mode = 'all';
      this.rebuild();
      this.camera = fitCamera(this.visible, this.width, this.height);
      this.baseScale = this.camera.scale;
      this.invalidate();
    }

    zoom(factor, anchor = {x: this.width / 2, y: this.height / 2}) {
      this.camera = zoomCamera(this.camera, factor, anchor);
      this.invalidate();
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return; // Mobile tab is currently hidden.
      const oldWidth = this.width, oldHeight = this.height;
      this.width = rect.width;
      this.height = rect.height;
      this.baseScale = fitCamera(this.nodes, this.width, this.height).scale;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = Math.round(this.width * dpr);
      this.canvas.height = Math.round(this.height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!this.ready) {
        this.camera = fitCamera(this.visible, this.width, this.height);
        this.ready = true;
      } else {
        // Preserve the current world center; resizing must not undo a pan or selection.
        this.camera.x += (this.width - oldWidth) / 2;
        this.camera.y += (this.height - oldHeight) / 2;
      }
      this.invalidate();
    }

    invalidate() {
      if (this.frame) return;
      this.frame = requestAnimationFrame(() => { this.frame = null; this.draw(); });
    }

    shape(shape, x, y, r, c = this.ctx) {
      c.beginPath();
      if (shape === 'circle') c.arc(x, y, r, 0, 2 * Math.PI);
      else if (shape === 'square') c.rect(x - r, y - r, r * 2, r * 2);
      else if (shape === 'cross') {
        c.moveTo(x - r, y); c.lineTo(x + r, y); c.moveTo(x, y - r); c.lineTo(x, y + r);
      } else {
        const count = shape === 'triangle' ? 3 : shape === 'diamond' ? 4 : 6;
        for (let i = 0; i < count; i++) {
          const angle = -Math.PI / 2 + i * 2 * Math.PI / count;
          const xx = x + r * Math.cos(angle), yy = y + r * Math.sin(angle);
          if (!i) c.moveTo(xx, yy); else c.lineTo(xx, yy);
        }
        c.closePath();
      }
    }

    createNodeSprites() {
      // Six small cached textures: no per-node blur or gradients during pan/zoom.
      const sprites = new Map();
      for (const [role, style] of Object.entries(roles)) {
        const sprite = this.canvas.ownerDocument.createElement('canvas');
        sprite.width = sprite.height = 112;
        const c = sprite.getContext('2d');
        const rgb = style.color.match(/\w\w/g).map(channel => parseInt(channel, 16));
        const shade = factor => `rgb(${rgb.map(channel => Math.round(channel * factor)).join(',')})`;
        const glow = c.createRadialGradient(56, 56, 10, 56, 56, 54);
        glow.addColorStop(0, style.color + '80');
        glow.addColorStop(.4, style.color + '2e');
        glow.addColorStop(1, style.color + '00');
        c.fillStyle = glow; c.fillRect(0, 0, 112, 112);
        this.shape(style.shape, 56, 56, 24, c);
        if (style.shape === 'cross') {
          c.strokeStyle = style.color; c.lineWidth = 4; c.lineCap = 'round'; c.stroke();
        } else {
          const body = c.createRadialGradient(47, 46, 1, 56, 59, 32);
          body.addColorStop(0, '#f1fbff');
          body.addColorStop(.24, style.color);
          body.addColorStop(.62, shade(.72));
          body.addColorStop(1, shade(.25));
          c.fillStyle = body; c.fill();
          c.strokeStyle = style.color + 'cc'; c.lineWidth = 1.2; c.stroke();
          c.save(); c.clip();
          const shine = c.createRadialGradient(48, 45, 0, 48, 45, 12);
          shine.addColorStop(0, '#ffffffaa'); shine.addColorStop(1, '#ffffff00');
          c.fillStyle = shine; c.fillRect(32, 32, 48, 48);
          c.restore();
        }
        sprites.set(role, sprite);
      }
      return sprites;
    }

    drawEdge(e) {
      const c = this.ctx, a = this.screen(e.a), b = this.screen(e.b);
      if ((a.x < -20 && b.x < -20) || (a.y < -20 && b.y < -20)
          || (a.x > this.width + 20 && b.x > this.width + 20)
          || (a.y > this.height + 20 && b.y > this.height + 20)) return;
      const active = this.activeEdge(e), path = this.mode === 'path';
      const focused = this.selected !== null || this.cluster !== null;
      const opacity = path || active ? .88 : focused ? .07 : .26;
      const color = path ? '#ffd070' : active && this.selected
        ? (e.dst === this.selected ? '#fbc775' : '#69e0ff') : '#68b8db';
      let angle, tip;
      if (e.src === e.dst) {
        const r = this.radius(e.a) + 6;
        c.beginPath(); c.arc(a.x + r, a.y - r, r, .4, 2 * Math.PI);
        angle = Math.PI / 2;
        tip = {x: a.x + 2 * r, y: a.y - r};
      } else {
        angle = Math.atan2(b.y - a.y, b.x - a.x);
        const start = this.radius(e.a) + 1, end = this.radius(e.b) + 2;
        if (Math.hypot(a.x - b.x, a.y - b.y) < start + end) return;
        tip = {x: b.x - Math.cos(angle) * end, y: b.y - Math.sin(angle) * end};
        c.beginPath(); c.moveTo(a.x + Math.cos(angle) * start, a.y + Math.sin(angle) * start);
        c.lineTo(tip.x, tip.y);
      }
      c.strokeStyle = color;
      if (active || path) {
        // A translucent outer stroke creates a laser halo without expensive blur.
        c.globalAlpha = opacity * .14; c.lineWidth = e.stroke + 3; c.stroke();
      }
      c.globalAlpha = opacity; c.lineWidth = e.stroke; c.stroke();
      if (active || path) {
        c.strokeStyle = '#e4faff'; c.globalAlpha = .35;
        c.lineWidth = Math.min(.65, e.stroke * .45); c.stroke();
      }
      c.globalAlpha = opacity; c.fillStyle = color;
      const size = active || path ? 6 : 3;
      c.beginPath(); c.moveTo(tip.x, tip.y);
      c.lineTo(tip.x - size * Math.cos(angle - .5), tip.y - size * Math.sin(angle - .5));
      c.lineTo(tip.x - size * Math.cos(angle + .5), tip.y - size * Math.sin(angle + .5));
      c.closePath(); c.fill();
    }

    draw() {
      const start = performance.now(), c = this.ctx, cam = this.camera;
      c.clearRect(0, 0, this.width, this.height);
      const focused = this.selected !== null || this.cluster !== null;
      if (this.mode !== 'path') {
        for (const h of this.hulls) {
          if (!this.visibleGroups.has(h.id)) continue;
          const x = h.left * cam.scale + cam.x, y = h.top * cam.scale + cam.y;
          const w = (h.right - h.left) * cam.scale, height = (h.bottom - h.top) * cam.scale;
          if (x > this.width || y > this.height || x + w < 0 || y + height < 0) continue;
          c.globalAlpha = this.cluster === h.id ? 1 : focused ? .3 : .8;
          c.fillStyle = this.cluster === h.id ? '#163044' : '#10203680';
          c.strokeStyle = this.cluster === h.id ? '#65bcd4' : '#29425e';
          c.lineWidth = this.cluster === h.id ? 1.5 : .7;
          c.beginPath(); c.roundRect(x, y, w, height, Math.min(14, w / 3, height / 3));
          c.fill(); c.stroke();
        }
      }
      for (const group of this.links) for (const e of group) this.drawEdge(e);
      // Draw the selected node last to keep its ring visible in dense communities.
      for (const n of this.visible) if (n.gid !== this.selected) this.drawNode(n, focused);
      if (this.ids.has(this.selected)) {
        const n = this.map.get(this.selected);
        this.drawNode(n, focused);
        this.drawLabel(n);
      }
      c.globalAlpha = 1;
      this.callbacks.camera?.(cam.scale / this.baseScale);
      this.canvas.dataset.renderMs = (performance.now() - start).toFixed(2);
      this.canvas.dataset.visibleNodes = String(this.visible.length);
    }

    drawNode(n, focused) {
      const c = this.ctx, p = this.screen(n), r = this.radius(n);
      if (p.x < -32 || p.y < -32 || p.x > this.width + 32 || p.y > this.height + 32) return;
      const active = this.related.has(n.gid) || this.mode === 'path';
      c.globalAlpha = n.gid === this.selected ? 1 : focused && !active ? .12 : n.role === 'peripheral' ? .46 : .95;
      const side = r * 112 / 24;
      c.drawImage(this.nodeSprites.get(n.role), p.x - side / 2, p.y - side / 2, side, side);
      if (n.is_seed || n.gid === this.selected) {
        c.beginPath(); c.arc(p.x, p.y, r + (n.gid === this.selected ? 4 : 2), 0, Math.PI * 2);
        c.lineWidth = n.gid === this.selected ? 2 : 1;
        c.strokeStyle = n.gid === this.selected ? '#a0edff' : '#bad0eb'; c.stroke();
        if (n.gid === this.selected) {
          c.globalAlpha = .22; c.lineWidth = 5; c.stroke();
        }
      }
    }

    drawLabel(n) {
      const c = this.ctx, p = this.screen(n);
      if (p.x < 0 || p.y < 0 || p.x > this.width || p.y > this.height) return;
      c.globalAlpha = 1;
      c.font = '12px system-ui';
      const width = Math.min(this.width - 12, Math.max(c.measureText(n.gid).width, c.measureText(roles[n.role].label).width) + 16);
      const x = clamp(p.x + 14, 6, Math.max(6, this.width - width - 6));
      const y = clamp(p.y - 48, 6, Math.max(6, this.height - 46));
      c.fillStyle = '#101d30f5'; c.strokeStyle = '#3f738c'; c.lineWidth = 1;
      c.beginPath(); c.roundRect(x, y, width, 40, 5); c.fill(); c.stroke();
      c.fillStyle = '#e4ecf9'; c.fillText(n.gid, x + 8, y + 16);
      c.fillStyle = '#a5bdd6'; c.fillText(roles[n.role].label, x + 8, y + 32);
    }

    hit(point) {
      let nearest = null, distance = Infinity;
      for (const n of this.visible) {
        const p = this.screen(n), d = Math.hypot(p.x - point.x, p.y - point.y);
        if (d < this.radius(n) + 5 && d < distance) { nearest = n; distance = d; }
      }
      if (nearest) return {node: nearest};
      if (this.mode === 'path') return {};
      const x = (point.x - this.camera.x) / this.camera.scale;
      const y = (point.y - this.camera.y) / this.camera.scale;
      const cluster = this.hulls.find(h => this.visibleGroups.has(h.id) && x >= h.left && x <= h.right && y >= h.top && y <= h.bottom);
      return cluster ? {cluster} : {};
    }

    bindEvents() {
      const point = e => {
        const r = this.canvas.getBoundingClientRect();
        return {x: e.clientX - r.left, y: e.clientY - r.top};
      };
      this.canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? this.height : 1);
        this.zoom(Math.exp(-clamp(delta, -500, 500) * .0015), point(e));
        this.callbacks.hover?.({}, point(e));
      }, {passive: false});
      this.canvas.addEventListener('pointerdown', e => {
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        this.canvas.setPointerCapture(e.pointerId);
        this.gesture.down(e.pointerId, point(e));
        this.callbacks.hover?.({}, point(e));
      });
      this.canvas.addEventListener('pointermove', e => {
        const p = point(e);
        if (this.gesture.points.has(e.pointerId)) {
          this.camera = this.gesture.move(e.pointerId, p, this.camera);
          this.invalidate();
        } else if (e.pointerType !== 'touch') this.callbacks.hover?.(this.hit(p), p);
      });
      this.canvas.addEventListener('pointerup', e => {
        if (this.gesture.up(e.pointerId)) {
          const target = this.hit(point(e));
          if (target.node) this.callbacks.choose?.(target.node.gid);
          else if (target.cluster) this.callbacks.cluster?.(target.cluster.id);
        }
      });
      for (const event of ['pointercancel', 'lostpointercapture']) {
        this.canvas.addEventListener(event, e => this.gesture.up(e.pointerId, true));
      }
      this.canvas.addEventListener('pointerleave', () => this.callbacks.hover?.({}, {x: 0, y: 0}));
      this.canvas.addEventListener('keydown', e => {
        if (e.key === '+' || e.key === '=') this.zoom(1.3);
        else if (e.key === '-') this.zoom(1 / 1.3);
        else if (e.key === 'Home') this.callbacks.reset?.();
        else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
          const shift = 50;
          this.camera.x += e.key === 'ArrowLeft' ? shift : e.key === 'ArrowRight' ? -shift : 0;
          this.camera.y += e.key === 'ArrowUp' ? shift : e.key === 'ArrowDown' ? -shift : 0;
          this.invalidate();
        } else return;
        e.preventDefault();
      });
    }
  }
  return {roles, limits, clamp, zoomCamera, fitCamera, nodeCamera, edgeWidths, Gesture, GraphView};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = GraphUI;
