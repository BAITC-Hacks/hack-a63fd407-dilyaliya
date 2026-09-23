'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {zoomCamera, fitCamera, nodeCamera, edgeWidths, Gesture, limits} = require('../app/graph.js');

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
const worldAt = (camera, point) => ({x: (point.x - camera.x) / camera.scale, y: (point.y - camera.y) / camera.scale});

test('wheel zoom preserves the world point under the cursor, including both limits', () => {
  const camera = {scale: .4, x: -230, y: 18}, anchor = {x: 370, y: 125};
  const before = worldAt(camera, anchor);
  for (const factor of [1.3, .2, 1e9, 1e-9]) {
    const next = zoomCamera(camera, factor, anchor);
    const after = worldAt(next, anchor);
    close(after.x, before.x); close(after.y, before.y);
    assert.ok(next.scale >= limits.min && next.scale <= limits.max);
  }
});

test('fit contains distant neighbors and centers the selected node', () => {
  const points = [{x: -1200, y: 300}, {x: 700, y: -1800}, {x: 200, y: 100}];
  const center = points[2], width = 680, height = 430;
  const camera = fitCamera(points, width, height, center);
  close(center.x * camera.scale + camera.x, width / 2);
  close(center.y * camera.scale + camera.y, height / 2);
  for (const point of points) {
    const x = point.x * camera.scale + camera.x, y = point.y * camera.scale + camera.y;
    assert.ok(x >= 20 && x <= width - 20);
    assert.ok(y >= 30 && y <= height - 30);
  }
});

test('isolated node and empty graph have finite useful cameras', () => {
  for (const points of [[], [{x: 3300, y: 2970}]]) {
    const camera = fitCamera(points, 390, 280);
    assert.ok(Object.values(camera).every(Number.isFinite));
    assert.ok(camera.scale > 0 && camera.scale <= limits.max);
  }
});

test('automatic node selection stays close even when a counterparty is far away', () => {
  const node = {x: 1000, y: 660};
  const camera = nodeCamera(node, [node, {x: -9000, y: 10000}], 600, 400);
  assert.ok(camera.scale >= .5);
  close(camera.x + node.x * camera.scale, 300);
  close(camera.y + node.y * camera.scale, 200);
});

test('edge widths preserve order but cap outliers without changing amounts', () => {
  const amounts = Array.from({length: 99}, (_, i) => (i + 1) * 5000).concat(1e10);
  const original = [...amounts];
  const {cap, width} = edgeWidths(amounts);
  assert.equal(cap, 475000);
  assert.equal(width(0), .6); assert.equal(width(1e10), 2.8);
  assert.ok(width(10000) < width(20000));
  assert.ok(amounts.every(amount => width(amount) >= .6 && width(amount) <= 2.8));
  assert.deepEqual(amounts, original);
  assert.ok(Number.isFinite(edgeWidths([]).width(0)));
});

test('drag translates the camera and cannot select a node when released', () => {
  const gesture = new Gesture(), camera = {scale: .3, x: 20, y: 40};
  gesture.down(1, {x: 100, y: 80});
  const next = gesture.move(1, {x: 155, y: 50}, camera);
  assert.deepEqual(next, {scale: .3, x: 75, y: 10});
  assert.equal(gesture.up(1), false);
});

test('pinch zoom preserves the world point under the moving two-finger midpoint', () => {
  const gesture = new Gesture();
  const camera = {scale: .2, x: 10, y: 20};
  gesture.down(1, {x: 100, y: 100}); gesture.down(2, {x: 200, y: 100});
  const before = worldAt(camera, {x: 150, y: 100});
  const next = gesture.move(2, {x: 300, y: 140}, camera);
  const after = worldAt(next, {x: 200, y: 120});
  close(after.x, before.x); close(after.y, before.y);
  close(next.scale, .2 * Math.hypot(200, 40) / 100);
  assert.equal(gesture.up(2), false); assert.equal(gesture.up(1), false);
});

test('pointer cancellation never clicks, while the next independent tap does', () => {
  const gesture = new Gesture();
  gesture.down(1, {x: 0, y: 0});
  assert.equal(gesture.up(1, true), false);
  assert.equal(gesture.up(1), false);
  gesture.down(2, {x: 12, y: 15});
  assert.equal(gesture.up(2), true);
});
