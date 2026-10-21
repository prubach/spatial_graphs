// Keeps the 2D crossing markers in sync when nodes are dragged.
(function () {
  function cross(a, b) { return a[0] * b[1] - a[1] * b[0]; }

  function svgFor(under, over, color) {
    var ul = Math.hypot(under[0], under[1]) || 1, ol = Math.hypot(over[0], over[1]) || 1;
    var ux = under[0] / ul, uy = under[1] / ul, ox = over[0] / ol, oy = over[1] / ol;
    var f = function (x) { return x.toFixed(2); };
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">' +
      '<path d="M ' + f(12 - 7.5 * ux) + ' ' + f(12 - 7.5 * uy) + ' L ' + f(12 + 7.5 * ux) + ' ' + f(12 + 7.5 * uy) +
      '" stroke="white" stroke-width="9" stroke-linecap="round"/>' +
      '<path d="M ' + f(12 - 9 * ox) + ' ' + f(12 - 9 * oy) + ' L ' + f(12 + 9 * ox) + ' ' + f(12 + 9 * oy) +
      '" stroke="' + color + '" stroke-width="5" stroke-linecap="round"/></svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  function update(cy) {
    cy.batch(function () {
      cy.nodes('.crossing-marker').forEach(function (m) {
        var d = m.data();
        var p = cy.getElementById(d.e1[0]), q = cy.getElementById(d.e1[1]);
        var c = cy.getElementById(d.e2[0]), e = cy.getElementById(d.e2[1]);
        if (!p.length || !q.length || !c.length || !e.length) { m.style('display', 'none'); return; }
        var P = p.position(), Q = q.position(), C = c.position(), E = e.position();
        var r = [Q.x - P.x, Q.y - P.y], s = [E.x - C.x, E.y - C.y];
        var den = cross(r, s);
        if (Math.abs(den) < 1e-12) { m.style('display', 'none'); return; }
        var off = [C.x - P.x, C.y - P.y];
        var t = cross(off, s) / den, u = cross(off, r) / den;
        if (!(t > 1e-9 && t < 1 - 1e-9 && u > 1e-9 && u < 1 - 1e-9)) { m.style('display', 'none'); return; }
        var z1 = d.z1[0] + t * (d.z1[1] - d.z1[0]), z2 = d.z2[0] + u * (d.z2[1] - d.z2[0]);
        var firstOver = z1 > z2;
        m.position({ x: P.x + t * r[0], y: P.y + t * r[1] });
        m.data('image', svgFor(firstOver ? s : r, firstOver ? r : s, firstOver ? d.c1 : d.c2));
        m.style('display', 'element');
      });
    });
  }

  function attach() {
    var el = document.getElementById('graph');
    var cy = el && el._cyreg && el._cyreg.cy;
    if (cy && !cy._crossingSync) {
      cy._crossingSync = true;
      cy.on('position drag free', 'node', function (ev) {
        if (!ev.target.hasClass('crossing-marker')) update(cy);
      });
    }
  }
  setInterval(attach, 500);
})();
