
# venous_valve_flask_app_4_geometry_generator_extAE_mesh_inline_full2D.py
# Inline mesh view confined to the FULL 2D lumen (left+right) with top/bottom closures.
#
from flask import Flask, render_template_string, request, Response, jsonify
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:
    import triangle as tr
    HAS_TRIANGLE = True
except Exception:
    HAS_TRIANGLE = False

app = Flask(__name__)

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Venous Valve Geometry Simulator (A1/E1 + Full 2D Meshing)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <style>
    body { padding: 1rem; }
    .controls { gap: 1rem; margin-bottom: 1rem; }
    .controls .form-control { width: 220px; }
    .controls .form-label { font-size: .9rem; }
    .card { border-radius: 1rem; }
    .param-card { border: 1px solid #e5e7eb; }
    .param-card .card-header { background: #f8fafc; font-weight: 600; }
    img.plot2d { display:block; max-width: 60%; width: 60%; height: auto; margin: 0.5rem auto; border:1px solid #ddd; border-radius: 10px; }
    #plot3d { width: 100%; height: 520px; border:1px solid #ddd; border-radius: 10px; }
    .section-title { font-size: 1.1rem; font-weight: 600; }
    .cam-buttons .btn { margin-right: .5rem; margin-bottom: .5rem; }
    .toggle-btn { width: 100%; display: flex; justify-content: space-between; align-items: center; }
    .toggle-btn .arrow { transition: transform .2s ease; }
    .toggle-btn.collapsed .arrow { transform: rotate(-90deg); }
    .hint { color:#555; font-size:.9rem; }
    .mesh-frame { width: 100%; height: 520px; border: 1px solid #ddd; border-radius: 10px; background: #fff; }
  </style>
</head>
<body>
<div class="container-xxl">
  <h1 class="mb-3">Venous Valve Geometry Simulator</h1>

  <div class="card param-card mb-3 shadow-sm">
    <div class="card-header">Input Parameters</div>
    <div class="card-body">
      <form method="post" id="param-form">
        {% set vals = defaults if not results else results['inputs'] %}
        {% macro num_input(lbl, name, placeholder) -%}
          <div class="d-flex flex-column">
            <label class="form-label mb-1">{{ lbl }}</label>
            <input class="form-control form-control-sm" type="number" step="any" name="{{name}}"
                   value="{{ vals[name] }}" placeholder="{{placeholder}}" required>
          </div>
        {%- endmacro %}

        <div class="controls d-flex flex-wrap">
          {{ num_input("Leaflet inner-surface spacing at edge", "wE", "0.9") }}
          {{ num_input("Vein radius", "a", "1.0") }}
          {{ num_input("Sinus maximum radius", "b", "1.5") }}
          {{ num_input("Sinus length", "lam", "3.0") }}
        </div>

        <div class="controls d-flex flex-wrap align-items-end">
          {{ num_input("Axial distance beyond sinus maximum", "zD", "0.75") }}
          {{ num_input("Leaflet thickness", "tL", "0.03") }}
          {{ num_input("Fillet radius", "Rf", "0.2") }}
          {{ num_input("Bottom extension extA (+ = downward)", "extA", "0.0") }}
          {{ num_input("Top extension extE (+ = upward)", "extE", "0.0") }}

          <div class="d-flex flex-row align-items-end ms-auto" style="gap:.5rem;">
            <button class="btn btn-primary btn-sm" type="submit">Compute</button>
            <a id="dl-3d" class="btn btn-outline-success btn-sm" href="#" title="Download 3D STL">Download 3D STL</a>
          </div>
        </div>
      </form>
      <div class="hint mt-2">
        {% if has_triangle %}
          Meshing backend: <b>triangle</b> (quality constrained Delaunay).
        {% else %}
          Meshing backend: <b>fallback ear-clipping</b> (install <code>triangle</code> for high-quality meshes).
        {% endif %}
      </div>
    </div>
  </div>

  <script>
    (function() {
      const form = document.getElementById('param-form');
      const link = document.getElementById('dl-3d');
      function updateLink() {
        const fd = new FormData(form);
        const q = new URLSearchParams();
        ['a','b','lam','zD','wE','tL','Rf','extA','extE'].forEach(k => q.append(k, fd.get(k)));
        link.href = '/download_stl_3d?' + q.toString();
      }
      form.addEventListener('input', updateLink);
      window.addEventListener('load', updateLink);
    })();
  </script>

  {% if error %}
    <div class="alert alert-danger mt-2">{{ error }}</div>
  {% endif %}

  {% if results %}
  <div class="card shadow-sm mb-3">
    <div class="card-body">
      <div class="row g-3 align-items-start">
        <div class="col-12 col-xl-7">
          <div class="section-title mb-2">2D Visualization</div>
          <img class="plot2d" src="/plot?a={{results['inputs']['a']}}&b={{results['inputs']['b']}}&lam={{results['inputs']['lam']}}&zD={{results['inputs']['zD']}}&wE={{results['inputs']['wE']}}&tL={{results['inputs']['tL']}}&Rf={{results['inputs']['Rf']}}&extA={{results['inputs']['extA']}}&extE={{results['inputs']['extE']}}" alt="plot2d">
        </div>
        <div class="col-12 col-xl-5">
          <div class="d-flex justify-content-between align-items-center">
            <div class="section-title mb-2">3D Visualization (interactive)</div>
            <div class="cam-buttons">
              <button type="button" class="btn btn-outline-secondary btn-sm" id="view-xy">XY</button>
              <button type="button" class="btn btn-outline-secondary btn-sm" id="view-iso">Iso</button>
              <button type="button" class="btn btn-outline-secondary btn-sm" id="view-xz">XZ</button>
              <button type="button" class="btn btn-outline-secondary btn-sm" id="view-yz">YZ</button>
            </div>
          </div>
          <div id="plot3d"></div>
          <script>
            (function() {
              const q = new URLSearchParams({
                a: "{{results['inputs']['a']}}",
                b: "{{results['inputs']['b']}}",
                lam: "{{results['inputs']['lam']}}",
                zD: "{{results['inputs']['zD']}}",
                wE: "{{results['inputs']['wE']}}",
                tL: "{{results['inputs']['tL']}}",
                Rf: "{{results['inputs']['Rf']}}",
                extA: "{{results['inputs']['extA']}}",
                extE: "{{results['inputs']['extE']}}"
              });
              fetch("/plot3d_data?" + q.toString())
                .then(r => r.json())
                .then(data => {
                  const surface = { type: 'surface', x: data.X, y: data.Y, z: data.Z, showscale: false };
                  const layout = {
                    scene: {
                      xaxis: {title: 'x'},
                      yaxis: {title: 'y'},
                      zaxis: {title: 'z'},
                      aspectmode: 'data',
                      camera: { eye: {x: -0.001, y: 0, z: 2}, up: {x: 0, y: -1, z: 0}, center: {x: 0, y: 0, z: 0} },
                      projection: {type: 'orthographic'}
                    },
                    margin: {l:0, r:0, t:0, b:0}
                  };
                  Plotly.newPlot('plot3d', [surface], layout, {responsive: true, displaylogo: false});
                  function setCamera(eye, proj) {
                    const update = { 'scene.camera': {eye, up:{x:0,y:-1,z:0}, center:{x:0,y:0,z:0}} };
                    if (proj) update['scene.projection'] = {type: proj};
                    Plotly.relayout('plot3d', update);
                  }
                  document.getElementById('view-xy').onclick  = () => setCamera({x: -0.001, y: 0,   z: 2}, 'orthographic');
                  document.getElementById('view-iso').onclick = () => setCamera({x: -1.8,   y: 1.2, z: 1.6}, 'perspective');
                  document.getElementById('view-xz').onclick  = () => setCamera({x: -0.001, y: 2,   z: 0}, 'orthographic');
                  document.getElementById('view-yz').onclick  = () => setCamera({x: 2,      y: 0,   z: 0}, 'orthographic');
                })
                .catch(err => {
                  const el = document.getElementById('plot3d');
                  el.innerHTML = '<div class="text-danger">3D plot failed to load.</div>';
                  console.error(err);
                });
            })();
          </script>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-xl-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <button class="btn btn-outline-primary toggle-btn collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#left-data" aria-expanded="false">
            <span>Left-side data</span><span class="arrow">▼</span>
          </button>
          <div id="left-data" class="collapse mt-3">
            <div class="section-title mb-2">Points</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Point</th><th>x</th><th>y</th></tr></thead>
                <tbody>
                  {% for key, P in results['left']['points'] %}
                  <tr><td><b>{{key}}</b></td><td>{{"%.6f"|format(P[0])}}</td><td>{{"%.6f"|format(P[1])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class="section-title mt-3 mb-2">Arcs (radii & centers)</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Arc</th><th>R</th><th>Cx</th><th>Cy</th></tr></thead>
                <tbody>
                  {% for arc, A in results['left']['arcs'] %}
                  <tr><td><b>{{ arc }}</b></td><td>{{"%.9f"|format(A['R'])}}</td><td>{{"%.9f"|format(A['Cx'])}}</td><td>{{"%.9f"|format(A['Cy'])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class="section-title mt-3 mb-2">Segments</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Seg</th><th>x₀</th><th>y₀</th><th>x₁</th><th>y₁</th><th>L</th></tr></thead>
                <tbody>
                  {% for name, S in results['left']['segments'] %}
                  <tr><td><b>{{name}}</b></td><td>{{"%.6f"|format(S['x0'])}}</td><td>{{"%.6f"|format(S['y0'])}}</td><td>{{"%.6f"|format(S['x1'])}}</td><td>{{"%.6f"|format(S['y1'])}}</td><td>{{"%.6f"|format(S['L'])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- New inline mesh card -->
      {% if results %}
      <div class="card shadow-sm mt-3">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div class="section-title">2D Mesh (Full lumen)</div>
            <div class="hint">Backend: {{ 'triangle' if has_triangle else 'ear-clipping' }}</div>
          </div>
          <iframe
            class="mesh-frame"
            id="mesh-frame"
            src="/mesh2d_html_full?a={{results['inputs']['a']}}&b={{results['inputs']['b']}}&lam={{results['inputs']['lam']}}&zD={{results['inputs']['zD']}}&wE={{results['inputs']['wE']}}&tL={{results['inputs']['tL']}}&Rf={{results['inputs']['Rf']}}&extA={{results['inputs']['extA']}}&extE={{results['inputs']['extE']}}&min_angle=30&max_area="
          ></iframe>
          <div class="mt-2">
            <a class="btn btn-outline-secondary btn-sm"
               href="/download_mesh_msh_full?a={{results['inputs']['a']}}&b={{results['inputs']['b']}}&lam={{results['inputs']['lam']}}&zD={{results['inputs']['zD']}}&wE={{results['inputs']['wE']}}&tL={{results['inputs']['tL']}}&Rf={{results['inputs']['Rf']}}&extA={{results['inputs']['extA']}}&extE={{results['inputs']['extE']}}&min_angle=30&max_area="
               >Download 2D Mesh (.msh)</a>
          </div>
        </div>
      </div>
      {% endif %}

    </div>

    <div class="col-12 col-xl-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <button class="btn btn-outline-primary toggle-btn collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#right-data" aria-expanded="false">
            <span>Right-side data</span><span class="arrow">▼</span>
          </button>
          <div id="right-data" class="collapse mt-3">
            <div class="section-title mb-2">Points</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Point</th><th>x</th><th>y</th></tr></thead>
                <tbody>
                  {% for key, P in results['right']['points'] %}
                  <tr><td><b>{{key}}</b></td><td>{{"%.6f"|format(P[0])}}</td><td>{{"%.6f"|format(P[1])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class="section-title mt-3 mb-2">Arcs (radii & centers)</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Arc</th><th>R</th><th>Cx</th><th>Cy</th></tr></thead>
                <tbody>
                  {% for arc, A in results['right']['arcs'] %}
                  <tr><td><b>{{ arc }}</b></td><td>{{"%.9f"|format(A['R'])}}</td><td>{{"%.9f"|format(A['Cx'])}}</td><td>{{"%.9f"|format(A['Cy'])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class="section-title mt-3 mb-2">Segments</div>
            <div class="table-responsive">
              <table class="table table-sm table-striped align-middle">
                <thead><tr><th>Seg</th><th>x₀</th><th>y₀</th><th>x₁</th><th>y₁</th><th>L</th></tr></thead>
                <tbody>
                  {% for name, S in results['right']['segments'] %}
                  <tr><td><b>{{name}}</b></td><td>{{"%.6f"|format(S['x0'])}}</td><td>{{"%.6f"|format(S['y0'])}}</td><td>{{"%.6f"|format(S['x1'])}}</td><td>{{"%.6f"|format(S['y1'])}}</td><td>{{"%.6f"|format(S['L'])}}</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  {% endif %}

</div>
</body>
</html>
"""

# ---------- Geometry with extensions (same as previous app) ----------
def left_geometry(a, b, lam, zD, wE, tL, Rf, extA=0.0, extE=0.0):
    A  = (-a, 0.0)
    F  = (-a/2.0 - wE/4.0, lam/4.0 + zD/2.0)
    G  = (-wE/2.0, lam/2.0 + zD)
    H  = (-wE/2.0 - tL, lam/2.0 + zD)
    D  = (-(a + b)/2.0, 3.0*lam/4.0)
    E  = (-a, lam)
    A1 = (A[0], A[1] - extA)
    E1 = (E[0], E[1] + extE)

    def R_root(a, wE, lam, zD):
        denom = (a - wE/2.0)
        if denom <= 0:
            raise ValueError("Require a > w_E/2 for valid geometry.")
        return denom/4.0 + (lam + 2.0*zD)**2 / (16.0 * denom)

    RAF = R_root(a, wE, lam, zD)
    RFG = RAF
    RHI1 = RFG - tL
    if RHI1 <= 0:
        raise ValueError("Leaflet thickness too large: R_HI1 ≤ 0.")

    denom_ba = (b - a)
    if denom_ba <= 0:
        raise ValueError("Require b > a for valid sinus expansion.")
    RID = denom_ba/4.0 + lam**2 / (16.0 * denom_ba)
    RDE = RID

    C_AF  = (-a + RAF, 0.0)
    C_FG  = (-wE/2.0 - RFG, lam/2.0 + zD)
    C_HI1 = (-wE/2.0 - RFG, lam/2.0 + zD)
    C_ID  = (-b + RID, lam/2.0)
    C_DE  = (-a - RDE, lam)

    if Rf <= 0:
        raise ValueError("Fillet radius R_f must be positive.")
    if Rf >= min(RHI1, RID):
        raise ValueError("Fillet radius must be < min(R_HI1, R_I2D) for internal tangency.")

    def circle_intersection_centers(C1, r1, C2, r2):
        x1,y1 = C1; x2,y2 = C2
        dx, dy = x2-x1, y2-y1
        d = float(np.hypot(dx, dy))
        if d == 0:
            raise ValueError("Circle centers coincide; cannot place fillet.")
        if d > r1 + r2 or d < abs(r1 - r2):
            raise ValueError("No valid fillet center: circles do not intersect (check R_f).")
        a = (r1*r1 - r2*r2 + d*d) / (2*d)
        h_sq = r1*r1 - a*a
        h = 0.0 if h_sq < 0 else float(np.sqrt(h_sq))
        xm = x1 + a * dx / d
        ym = y1 + a * dy / d
        ux, uy = -dy/d, dx/d
        cA = (xm + h*ux, ym + h*uy)
        cB = (xm - h*ux, ym - h*uy)
        return cA, cB

    RHI1_minus = RHI1 - Rf
    RID_minus  = RID  - Rf
    cA, cB = circle_intersection_centers(C_HI1, RHI1_minus, C_ID, RID_minus)

    def tangent_point(Ci, Ri, Cf):
        vx, vy = Cf[0]-Ci[0], Cf[1]-Ci[1]
        d = float(np.hypot(vx, vy))
        if d == 0:
            raise ValueError("Degenerate fillet: center equals neighbor center.")
        ux, uy = vx/d, vy/d
        return (Ci[0] + Ri*ux, Ci[1] + Ri*uy)

    I1A = tangent_point(C_HI1, RHI1, cA)
    I2A = tangent_point(C_ID,  RID,  cA)
    I1B = tangent_point(C_HI1, RHI1, cB)
    I2B = tangent_point(C_ID,  RID,  cB)

    avg_y_A = (I1A[1] + I2A[1]) * 0.5
    avg_y_B = (I1B[1] + I2B[1]) * 0.5
    if avg_y_A <= avg_y_B:
        Cf, I1, I2 = cA, I1A, I2A
    else:
        Cf, I1, I2 = cB, I1B, I2B

    L_HG = float(np.hypot(G[0]-H[0], G[1]-H[1]))

    seg_HG  = ("HG",  {"x0": H[0], "y0": H[1], "x1": G[0], "y1": G[1], "L": L_HG})
    seg_AA1 = ("AA1", {"x0": A[0], "y0": A[1], "x1": A1[0], "y1": A1[1], "L": abs(extA)})
    seg_EE1 = ("EE1", {"x0": E[0], "y0": E[1], "x1": E1[0], "y1": E1[1], "L": abs(extE)})
    segments = [seg_HG, seg_AA1, seg_EE1]

    points = [("A1", A1), ("A", A), ("F", F), ("G", G), ("H", H),
              ("I1", I1), ("I2", I2), ("D", D), ("E", E), ("E1", E1)]
    arcs = [
        ("AF",   {"R": RAF,  "Cx": C_AF[0],  "Cy": C_AF[1]}),
        ("FG",   {"R": RFG,  "Cx": C_FG[0],  "Cy": C_FG[1]}),
        ("HI1",  {"R": RHI1, "Cx": C_HI1[0], "Cy": C_HI1[1]}),
        ("I1I2", {"R": Rf,   "Cx": Cf[0],    "Cy": Cf[1]}),
        ("I2D",  {"R": RID,  "Cx": C_ID[0],  "Cy": C_ID[1]}),
        ("DE",   {"R": RDE,  "Cx": C_DE[0],  "Cy": C_DE[1]}),
    ]
    return {"points": points, "arcs": arcs, "segments": segments}

def mirror_right(left):
    pts_r = [(name, (-x, y)) for name, (x,y) in left["points"]]
    arcs_r = [(name, {"R": data["R"], "Cx": -data["Cx"], "Cy": data["Cy"]}) for name, data in left["arcs"]]
    segs_r = [(name, {"x0": -S["x0"], "y0": S["y0"], "x1": -S["x1"], "y1": S["y1"], "L": S["L"]}) for name, S in left["segments"]]
    return {"points": pts_r, "arcs": arcs_r, "segments": segs_r}

def compute_both(a,b,lam,zD,wE,tL,Rf,extA=0.0,extE=0.0):
    left = left_geometry(a,b,lam,zD,wE,tL,Rf,extA,extE)
    right = mirror_right(left)
    return left, right

def parse_float(q, key, default):
    try: return float(q.get(key, default))
    except Exception: return float(default)

def arc_points(C, R, P0, P1, n=120):
    xC, yC = C
    a0 = float(np.arctan2(P0[1]-yC, P0[0]-xC))
    a1 = float(np.arctan2(P1[1]-yC, P1[0]-xC))
    da = a1 - a0
    while da > np.pi:  a1 -= 2*np.pi; da = a1 - a0
    while da < -np.pi: a1 += 2*np.pi; da = a1 - a0
    ts = np.linspace(a0, a1, n)
    xs = xC + R*np.cos(ts)
    ys = yC + R*np.sin(ts)
    return xs.tolist(), ys.tolist()

def build_side_profile_polyline(side):
    """Trace one wall from A1->A->...->E1 for either left or right dict."""
    P = dict(side["points"])
    A = {n:d for n,d in side["arcs"]}
    poly = []
    poly.append((P['A1'][0], P['A1'][1]))
    if (P['A1'][0], P['A1'][1]) != (P['A'][0], P['A'][1]):
        poly.append((P['A'][0], P['A'][1]))
    def append_arc(name, p0, p1, n=180):
        xs, ys = arc_points((A[name]['Cx'], A[name]['Cy']), A[name]['R'], P[p0], P[p1], n=n)
        if poly and (abs(poly[-1][0]-xs[0])>1e-9 or abs(poly[-1][1]-ys[0])>1e-9):
            poly.append((xs[0], ys[0]))
        poly.extend(zip(xs[1:], ys[1:]))
    append_arc('AF','A','F')
    append_arc('FG','F','G')
    for name,S in side["segments"]:
        if name=='HG':
            if poly and (abs(poly[-1][0]-P['G'][0])>1e-9 or abs(poly[-1][1]-P['G'][1])>1e-9):
                poly.append((P['G'][0], P['G'][1]))
            poly.append((S["x0"], S["y0"]))  # H
            break
    append_arc('HI1','H','I1')
    append_arc('I1I2','I1','I2')
    append_arc('I2D','I2','D')
    append_arc('DE','D','E')
    if poly and (abs(poly[-1][0]-P['E'][0])>1e-9 or abs(poly[-1][1]-P['E'][1])>1e-9):
        poly.append((P['E'][0], P['E'][1]))
    if (P['E'][0], P['E'][1]) != (P['E1'][0], P['E1'][1]):
        poly.append((P['E1'][0], P['E1'][1]))
    return np.array(poly, float)

def build_full_boundary_polyline(left, right):
    """Closed loop around lumen: up left wall, across top, down right wall, across bottom."""
    L = build_side_profile_polyline(left)   # A1_left -> ... -> E1_left
    R = build_side_profile_polyline(right)  # A1_right-> ... -> E1_right
    # Ensure order: start at A1_left, go up L to E1_left
    # Then top edge to E1_right
    top = np.array([[R[-1,0], R[-1,1]]])  # E1_right (last point in R)
    # Then go down the RIGHT wall from E1_right to A1_right (reverse R)
    R_down = R[::-1]
    # Bottom edge back to A1_left
    bottom = np.array([[L[0,0], L[0,1]]])  # A1_left
    loop = np.vstack([L, top, R_down, bottom])
    # Remove any duplicate consecutive points
    dedup = [loop[0]]
    for p in loop[1:]:
        if abs(p[0]-dedup[-1][0])>1e-12 or abs(p[1]-dedup[-1][1])>1e-12:
            dedup.append(p)
    return np.array(dedup, float)

# --------- Meshing helpers ---------
def ear_clipping_triangulate(poly):
    P = poly.tolist()
    n = len(P)
    if n < 3: return np.empty((0,3), dtype=int)
    def area2(P):
        A = 0.0
        for i in range(len(P)):
            x1,y1 = P[i]; x2,y2 = P[(i+1)%len(P)]
            A += x1*y2 - x2*y1
        return A/2.0
    if area2(P) < 0: P = P[::-1]
    V = list(range(len(P)))
    triangles = []
    def is_convex(i0,i1,i2):
        x1,y1 = P[i1]; x0,y0 = P[i0]; x2,y2 = P[i2]
        return (x1-x0)*(y2-y0) - (y1-y0)*(x2-x0) > 0
    def point_in_tri(pt, a,b,c):
        ax,ay = a; bx,by = b; cx,cy = c; px,py = pt
        v0 = (cx-ax, cy-ay); v1 = (bx-ax, by-ay); v2 = (px-ax, py-ay)
        den = v0[0]*v1[1]-v0[1]*v1[0]
        if abs(den) < 1e-12: return False
        u = (v2[0]*v1[1]-v2[1]*v1[0])/den
        v = (v0[0]*v2[1]-v0[1]*v2[0])/den
        return u >= 0 and v >= 0 and u+v <= 1
    count = 0
    while len(V) > 3 and count < 10000:
        ear_found = False
        for k in range(len(V)):
            i0 = V[(k-1)%len(V)]; i1 = V[k]; i2 = V[(k+1)%len(V)]
            if not is_convex(i0,i1,i2): continue
            a,b,c = P[i0],P[i1],P[i2]
            ok = True
            for j in V:
                if j in (i0,i1,i2): continue
                if point_in_tri(P[j], a,b,c):
                    ok = False; break
            if ok:
                triangles.append((i0,i1,i2))
                del V[k]
                ear_found = True
                break
        if not ear_found: break
        count += 1
    if len(V)==3:
        triangles.append(tuple(V))
    return np.array(triangles, dtype=int)

def generate_mesh_from_polyline(poly, min_angle=30.0, max_area=None):
    if HAS_TRIANGLE:
        segments = [(i, i+1) for i in range(len(poly)-1)]
        if tuple(poly[0]) != tuple(poly[-1]):
            segments.append((len(poly)-1, 0))
        A = dict(vertices=poly, segments=segments)
        opts = 'pq%g' % float(min_angle)
        if max_area is not None and str(max_area).strip() != '':
            try:
                Amax = float(max_area)
                if Amax > 0: opts += 'a%g' % Amax
            except Exception:
                pass
        m = tr.triangulate(A, opts)
        return m['vertices'], m['triangles']
    else:
        T = ear_clipping_triangulate(poly)
        return poly, T

def mesh_to_svg(vertices, triangles):
    if len(vertices)==0 or len(triangles)==0:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='600'></svg>"
    x = vertices[:,0]; y = vertices[:,1]
    xmin,xmax = float(x.min()), float(x.max())
    ymin,ymax = float(y.min()), float(y.max())
    pad = 0.05*max(xmax-xmin, ymax-ymin)
    xmin -= pad; xmax += pad; ymin -= pad; ymax += pad
    W,H = 900, 700
    def X(u): return (u - xmin)/(xmax - xmin + 1e-12) * W
    def Y(v): return H - (v - ymin)/(ymax - ymin + 1e-12) * H
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
             "<rect x='0' y='0' width='100%' height='100%' fill='white'/>"]
    for i,j,k in triangles.astype(int):
        parts.append(f"<polygon points='{X(vertices[i,0])},{Y(vertices[i,1])} {X(vertices[j,0])},{Y(vertices[j,1])} {X(vertices[k,0])},{Y(vertices[k,1])}' fill='#eaf2ff' stroke='#333' stroke-width='0.8'/>")
    parts.append("</svg>")
    return "\n".join(parts)

def mesh_to_msh(vertices, triangles):
    out = io.StringIO()
    out.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
    out.write("$Nodes\n")
    out.write(f"{len(vertices)}\n")
    for idx, (x,y) in enumerate(vertices, start=1):
        out.write(f"{idx} {x:.16e} {y:.16e} 0.0\n")
    out.write("$EndNodes\n")
    out.write("$Elements\n")
    out.write(f"{len(triangles)}\n")
    for eidx, (i,j,k) in enumerate(triangles.astype(int), start=1):
        out.write(f"{eidx} 2 0 {i+1} {j+1} {k+1}\n")
    out.write("$EndElements\n")
    return out.getvalue().encode("utf-8")

# --------- Plot route (unchanged) ---------
@app.route("/plot")
def plot():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)

    left, right = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
    Pleft = dict(left["points"]); Pright = dict(right["points"])
    Aleft = {n:d for n,d in left["arcs"]}; Aright = {n:d for n,d in right["arcs"]}

    fig, ax = plt.subplots(figsize=(7,6), dpi=140)
    def draw_side(P, A):
        def draw_arc(name, p0, p1):
            xs, ys = arc_points((A[name]['Cx'], A[name]['Cy']), A[name]['R'], P[p0], P[p1])
            ax.plot(xs, ys, lw=2)
        draw_arc('AF','A','F'); draw_arc('FG','F','G'); draw_arc('HI1','H','I1')
        draw_arc('I1I2','I1','I2'); draw_arc('I2D','I2','D'); draw_arc('DE','D','E')
    draw_side(Pleft, Aleft); draw_side(Pright, Aright)
    for side in (left, right):
        for name, S in side["segments"]:
            if name in ("HG", "AA1", "EE1"):
                ax.plot([S["x0"], S["x1"]], [S["y0"], S["y1"]], lw=2)
    for x,y in [p for _,p in left["points"]+right["points"]]:
        ax.plot(x,y,'ko',ms=3)
    ax.set_aspect('equal'); ax.grid(True, alpha=0.3); ax.set_xlabel('x'); ax.set_ylabel('y')
    xs_all = [p[0] for _,p in left["points"]+right["points"]]; ys_all = [p[1] for _,p in left["points"]+right["points"]]
    pad = 0.4*max(1,a)
    ymin = min(min(ys_all), -0.2*lam)
    ymax = max(max(ys_all), lam+0.2*lam)
    ax.set_xlim(min(xs_all)-pad, max(xs_all)+pad); ax.set_ylim(ymin, ymax)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

@app.route("/plot3d_data")
def plot3d_data():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)

    left, _ = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
    poly = build_side_profile_polyline(left)
    r = np.abs(poly[:,0]); y = poly[:,1]
    ntheta = 80; theta = np.linspace(0, 2*np.pi, ntheta)
    R, TH = np.meshgrid(r, theta, indexing='ij')
    Y = np.tile(y, (ntheta,1)).T; X = R * np.cos(TH); Z = R * np.sin(TH)
    return jsonify({"X": X.tolist(), "Y": Y.tolist(), "Z": Z.tolist()})

@app.route("/download_stl_3d")
def download_stl_3d():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)

    poly = build_side_profile_polyline(left_geometry(a,b,lam,zD,wE,tL,Rf,extA,extE))
    r = np.abs(poly[:,0]); y = poly[:,1]
    ntheta = 200; theta = np.linspace(0, 2*np.pi, ntheta, endpoint=False)
    V = [[(r[i]*np.cos(t), y[i], r[i]*np.sin(t)) for t in theta] for i in range(len(r))]
    tris = []
    rows = len(r); cols = len(theta)
    for i in range(rows-1):
        for j in range(cols):
          j2 = (j+1) % cols
          v00 = V[i][j];   v01 = V[i][j2]
          v10 = V[i+1][j]; v11 = V[i+1][j2]
          tris.append((v00, v10, v11))
          tris.append((v00, v11, v01))
    def write_ascii_stl(tris, name="mesh"):
        out = io.StringIO()
        out.write(f"solid {name}\n")
        for tri in tris:
            p0, p1, p2 = np.array(tri[0]), np.array(tri[1]), np.array(tri[2])
            n = np.cross(p1 - p0, p2 - p0)
            norm = np.linalg.norm(n); n = (n / norm) if norm>0 else np.array([0,0,1])
            out.write(f"  facet normal {n[0]:.7e} {n[1]:.7e} {n[2]:.7e}\n")
            out.write("    outer loop\n")
            for p in (p0,p1,p2):
                out.write(f"      vertex {p[0]:.7e} {p[1]:.7e} {p[2]:.7e}\n")
            out.write("    endloop\n")
            out.write("  endfacet\n")
        out.write(f"endsolid {name}\n")
        return out.getvalue().encode("utf-8")
    stl_bytes = write_ascii_stl(tris, name="venous_valve_3d_extAE")
    return Response(stl_bytes, mimetype='application/sla',
                    headers={"Content-Disposition":"attachment; filename=venous_valve_3d_extAE.stl"})

# --------- Full 2D mesh endpoints ---------

@app.route("/mesh2d_html_full")
def mesh2d_html_full():
    # identical parameters to mesh2d_svg_full
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)
    min_angle = parse_float(request.args, "min_angle", 30.0)
    max_area  = request.args.get("max_area", "").strip()

    left, right = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
    loop = build_full_boundary_polyline(left, right)
    V, T = generate_mesh_from_polyline(loop, min_angle=min_angle, max_area=max_area if max_area!='' else None)

    # Build an HTML page with inline SVG and + / - buttons that zoom by adjusting viewBox.
    x = V[:,0]; y = V[:,1]
    xmin,xmax = float(x.min()), float(x.max())
    ymin,ymax = float(y.min()), float(y.max())
    pad = 0.05*max(xmax-xmin, ymax-ymin)
    xmin -= pad; xmax += pad; ymin -= pad; ymax += pad
    W,H = 1000, 800
    def X(u): return (u - xmin)/(xmax - xmin + 1e-12) * W
    def Y(v): return H - (v - ymin)/(ymax - ymin + 1e-12) * H

    polys = []
    for i,j,k in T.astype(int):
        polys.append((X(V[i,0]),Y(V[i,1]),X(V[j,0]),Y(V[j,1]),X(V[k,0]),Y(V[k,1])))

    svg_polys = "\\n".join([
        f"<polygon points='{x1},{y1} {x2},{y2} {x3},{y3}' fill='#eaf2ff' stroke='#333' stroke-width='0.8'/>"
        for (x1,y1,x2,y2,x3,y3) in polys
    ])

    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'>
<style>
html,body{{margin:0;height:100%;background:#fff}}
#toolbar{{position:absolute;top:8px;left:8px;background:rgba(255,255,255,.95);border:1px solid #ccc;border-radius:8px;padding:6px}}
#toolbar button{{margin-right:6px}}
#view{{width:100%;height:100%;display:block}}
</style>
</head>
<body>
<div id="toolbar">
  <button id="zoom_in">+</button>
  <button id="zoom_out">−</button>
  <button id="reset">Reset</button>
</div>
<svg id="view" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="100%" height="100%" fill="white"/>
  {svg_polys}
</svg>
<script>
(function(){{
  const svg = document.getElementById('view');
  const orig = {{x:0,y:0,w:{W},h:{H}}};
  let vb = {{...orig}};
  function setVB(){{ svg.setAttribute('viewBox', `${{vb.x}} ${{vb.y}} ${{vb.w}} ${{vb.h}}`); }}
  setVB();
  function zoomAt(cx, cy, factor){{
    const x = cx*vb.w + vb.x;
    const y = cy*vb.h + vb.y;
    vb.x = x - (x - vb.x)*factor;
    vb.y = y - (y - vb.y)*factor;
    vb.w *= factor; vb.h *= factor;
    setVB();
  }}
  document.getElementById('zoom_in').onclick  = () => zoomAt(0.5,0.5,0.8);
  document.getElementById('zoom_out').onclick = () => zoomAt(0.5,0.5,1.25);
  document.getElementById('reset').onclick    = () => {{ vb={{...orig}}; setVB(); }};
}})();
</script>
</body></html>
"""
    return Response(html, mimetype="text/html")
@app.route("/mesh2d_svg_full")
def mesh2d_svg_full():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)
    min_angle = parse_float(request.args, "min_angle", 30.0)
    max_area  = request.args.get("max_area", "").strip()

    left, right = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
    loop = build_full_boundary_polyline(left, right)
    V, T = generate_mesh_from_polyline(loop, min_angle=min_angle, max_area=max_area if max_area!='' else None)
    svg = mesh_to_svg(V, T)
    return Response(svg, mimetype='image/svg+xml')

@app.route("/download_mesh_msh_full")
def download_mesh_msh_full():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)
    extA= parse_float(request.args, "extA", 0.0)
    extE= parse_float(request.args, "extE", 0.0)
    min_angle = parse_float(request.args, "min_angle", 30.0)
    max_area  = request.args.get("max_area", "").strip()

    left, right = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
    loop = build_full_boundary_polyline(left, right)
    V, T = generate_mesh_from_polyline(loop, min_angle=min_angle, max_area=max_area if max_area!='' else None)
    msh = mesh_to_msh(V, T)
    return Response(msh, mimetype='application/octet-stream',
                    headers={"Content-Disposition":"attachment; filename=venous_valve_2d_full_mesh.msh"})

@app.route("/", methods=["GET", "POST"])
def index():
    defaults = dict(a=1.0, b=1.5, lam=3.0, zD=0.75, wE=0.9, tL=0.03, Rf=0.2, extA=0.0, extE=0.0)
    error = None
    if request.method == "POST":
        try:
            a   = float(request.form["a"]); b   = float(request.form["b"])
            lam = float(request.form["lam"]); zD  = float(request.form["zD"])
            wE  = float(request.form["wE"]); tL  = float(request.form["tL"])
            Rf  = float(request.form["Rf"]); extA = float(request.form["extA"]); extE = float(request.form["extE"])
            left, right = compute_both(a,b,lam,zD,wE,tL,Rf,extA,extE)
            return render_template_string(PAGE, defaults=defaults, error=None,
                    results={"inputs": dict(a=a,b=b,lam=lam,zD=zD,wE=wE,tL=tL,Rf=Rf,extA=extA,extE=extE),
                             "left": left, "right": right},
                    has_triangle=HAS_TRIANGLE)
        except Exception as e:
            error = str(e)
            return render_template_string(PAGE, defaults=defaults, error=error, results=None, has_triangle=HAS_TRIANGLE)
    else:
        return render_template_string(PAGE, defaults=defaults, error=None, results=None, has_triangle=HAS_TRIANGLE)

if __name__ == "__main__":
    app.run(debug=True)
