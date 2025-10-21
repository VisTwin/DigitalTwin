# app.py
# Flask app to compute venous-valve points, arcs, fillet (I1,I2), straight HG,
# and now generate BOTH left and right halves (mirror-symmetric).
# Visualization shows both halves.
#
# Inputs: a, b, lam, zD, wE, tL, fillet radius Rf.

from flask import Flask, render_template_string, request, Response
import io, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = Flask(__name__)

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Venous Valve Geometry Calculator</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { padding: 2rem; }
    .card { border-radius: 1rem; }
    .table thead th { white-space: nowrap; }
    .small-note { font-size: .9rem; color: #555; }
    img.plot { max-width: 100%; height: auto; border:1px solid #ddd; border-radius: 10px; }
  </style>
</head>
<body>
<div class="container-xxl">
  <h1 class="mb-3">Venous Valve Geometry Calculator</h1>
  <p class="text-muted">Left &amp; right halves; fillet on bottom branch; straight segment H–G included.</p>

  <form class="row gy-3" method="post">
    {% set vals = defaults if not results else results['inputs'] %}
    {% macro num_input(lbl, name, placeholder) -%}
      <div class="col-12 col-sm-6 col-md-4 col-xl-3">
        <label class="form-label">{{ lbl }}</label>
        <input class="form-control" type="number" step="any" name="{{name}}"
               value="{{ vals[name] }}" placeholder="{{placeholder}}" required>
      </div>
    {%- endmacro %}

    {{ num_input("Vein radius a", "a", "1.0") }}
    {{ num_input("Sinus max radius b", "b", "1.5") }}
    {{ num_input("Sinus length λ", "lam", "3.0") }}
    {{ num_input("Axial distance z_D", "zD", "0.75") }}
    {{ num_input("Leaflet inner-edge spacing w_E", "wE", "0.9") }}
    {{ num_input("Leaflet thickness t_L", "tL", "0.03") }}
    {{ num_input("Fillet radius R_f (HI1↔I2D)", "Rf", "0.2") }}

    <div class="col-12">
      <button class="btn btn-primary btn-lg">Compute</button>
    </div>
  </form>

  {% if error %}
    <div class="alert alert-danger mt-3">{{ error }}</div>
  {% endif %}

  {% if results %}
  <hr class="my-4">
  <div class="row g-4">
    <div class="col-12 col-xl-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h5 class="card-title">Left-side Points</h5>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
              <thead><tr><th>Point</th><th>x</th><th>y</th></tr></thead>
              <tbody>
                {% for key, P in results['left']['points'] %}
                <tr><td><b>{{key}}</b></td><td>{{"%.6f"|format(P[0])}}</td><td>{{"%.6f"|format(P[1])}}</td></tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <h6 class="mt-4">Left arcs (radii & centers)</h6>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
              <thead><tr><th>Arc</th><th>R</th><th>Cx</th><th>Cy</th></tr></thead>
              <tbody>
                {% for arc, A in results['left']['arcs'] %}
                <tr><td><b>{{ arc }}</b></td><td>{{"%.9f"|format(A['R'])}}</td><td>{{"%.9f"|format(A['Cx'])}}</td><td>{{"%.9f"|format(A['Cy'])}}</td></tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <h6 class="mt-4">Left segments</h6>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
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

    <div class="col-12 col-xl-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h5 class="card-title">Right-side Points</h5>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
              <thead><tr><th>Point</th><th>x</th><th>y</th></tr></thead>
              <tbody>
                {% for key, P in results['right']['points'] %}
                <tr><td><b>{{key}}</b></td><td>{{"%.6f"|format(P[0])}}</td><td>{{"%.6f"|format(P[1])}}</td></tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <h6 class="mt-4">Right arcs (radii & centers)</h6>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
              <thead><tr><th>Arc</th><th>R</th><th>Cx</th><th>Cy</th></tr></thead>
              <tbody>
                {% for arc, A in results['right']['arcs'] %}
                <tr><td><b>{{ arc }}</b></td><td>{{"%.9f"|format(A['R'])}}</td><td>{{"%.9f"|format(A['Cx'])}}</td><td>{{"%.9f"|format(A['Cy'])}}</td></tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <h6 class="mt-4">Right segments</h6>
          <div class="table-responsive">
            <table class="table table-striped align-middle">
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

    <div class="col-12">
      <div class="card shadow-sm mt-2">
        <div class="card-body">
          <h5 class="card-title">Visualization (both halves)</h5>
          <img class="plot" src="/plot?a={{results['inputs']['a']}}&b={{results['inputs']['b']}}&lam={{results['inputs']['lam']}}&zD={{results['inputs']['zD']}}&wE={{results['inputs']['wE']}}&tL={{results['inputs']['tL']}}&Rf={{results['inputs']['Rf']}}" alt="plot">
        </div>
      </div>
    </div>
  </div>
  {% endif %}

</div>
</body>
</html>
"""

# ---------- core geometry (left-side) ----------
def left_geometry(a, b, lam, zD, wE, tL, Rf):
    A = (-a, 0.0)
    F = (-a/2.0 - wE/4.0, lam/4.0 + zD/2.0)
    G = (-wE/2.0, lam/2.0 + zD)
    H = (-wE/2.0 - tL, lam/2.0 + zD)
    D = (-(a + b)/2.0, 3.0*lam/4.0)
    E = (-a, lam)

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
        raise ValueError("Fillet radius must be < min(R_HI1, R_I2D).")

    def circle_intersection_centers(C1, r1, C2, r2):
        x1,y1 = C1; x2,y2 = C2
        dx, dy = x2-x1, y2-y1
        d = math.hypot(dx, dy)
        if d == 0:
            raise ValueError("Circle centers coincide; cannot place fillet.")
        if d > r1 + r2 or d < abs(r1 - r2):
            raise ValueError("No valid fillet center: circles do not intersect (check R_f).")
        a = (r1*r1 - r2*r2 + d*d) / (2*d)
        h_sq = r1*r1 - a*a
        h = 0.0 if h_sq < 0 else math.sqrt(h_sq)
        xm = x1 + a * dx / d
        ym = y1 + a * dy / d
        ux, uy = -dy/d, dx/d
        cA = (xm + h*ux, ym + h*uy); cB = (xm - h*ux, ym - h*uy)
        return cA, cB

    r1 = RHI1 - Rf; r2 = RID - Rf
    cA, cB = circle_intersection_centers(C_HI1, r1, C_ID, r2)

    def tangent_point(Ci, Ri, Cf):
        vx, vy = Cf[0]-Ci[0], Cf[1]-Ci[1]; d = math.hypot(vx, vy)
        if d == 0: raise ValueError("Degenerate fillet: center equals neighbor center.")
        ux, uy = vx/d, vy/d
        return (Ci[0] + Ri*ux, Ci[1] + Ri*uy)

    I1A = tangent_point(C_HI1, RHI1, cA); I2A = tangent_point(C_ID, RID, cA)
    I1B = tangent_point(C_HI1, RHI1, cB); I2B = tangent_point(C_ID, RID, cB)
    avg_y_A = 0.5*(I1A[1]+I2A[1]); avg_y_B = 0.5*(I1B[1]+I2B[1])
    if avg_y_A <= avg_y_B:
        Cf, I1, I2 = cA, I1A, I2A
    else:
        Cf, I1, I2 = cB, I1B, I2B

    L_HG = math.hypot(G[0]-H[0], G[1]-H[1])
    segments = [("HG", {"x0": H[0], "y0": H[1], "x1": G[0], "y1": G[1], "L": L_HG})]

    points = [("A", A), ("F", F), ("G", G), ("H", H), ("I1", I1), ("I2", I2), ("D", D), ("E", E)]
    arcs = [
        ("AF",   {"R": RAF,  "Cx": C_AF[0],  "Cy": C_AF[1]}),
        ("FG",   {"R": RFG,  "Cx": C_FG[0],  "Cy": C_FG[1]}),
        ("HI1",  {"R": RHI1, "Cx": C_HI1[0], "Cy": C_HI1[1]}),
        ("I1I2", {"R": Rf,   "Cx": Cf[0],    "Cy": Cf[1]}),
        ("I2D",  {"R": RID,  "Cx": C_ID[0],  "Cy": C_ID[1]}),
        ("DE",   {"R": RDE,  "Cx": C_DE[0],  "Cy": C_DE[1]}),
    ]
    return {"points": points, "arcs": arcs, "segments": segments}

# ---------- mirror to right-side ----------
def mirror_right(left):
    # mirror x -> -x, keep y, same radii
    pts_r = [(name, (-x, y)) for name, (x,y) in left["points"]]
    arcs_r = []
    for name, data in left["arcs"]:
        arcs_r.append((name, {"R": data["R"], "Cx": -data["Cx"], "Cy": data["Cy"]}))
    segs_r = []
    for name, S in left["segments"]:
        segs_r.append((name, {"x0": -S["x0"], "y0": S["y0"], "x1": -S["x1"], "y1": S["y1"], "L": S["L"]}))
    return {"points": pts_r, "arcs": arcs_r, "segments": segs_r}

def compute_both(a,b,lam,zD,wE,tL,Rf):
    left = left_geometry(a,b,lam,zD,wE,tL,Rf)
    right = mirror_right(left)
    return left, right

def parse_float(q, key, default):
    try: return float(q.get(key, default))
    except Exception: return float(default)

def arc_points(C, R, P0, P1, n=120):
    xC, yC = C
    a0 = math.atan2(P0[1]-yC, P0[0]-xC)
    a1 = math.atan2(P1[1]-yC, P1[0]-xC)
    da = a1 - a0
    while da > math.pi:  a1 -= 2*math.pi; da = a1 - a0
    while da < -math.pi: a1 += 2*math.pi; da = a1 - a0
    ts = [a0 + i*da/(n-1) for i in range(n)]
    xs = [xC + R*math.cos(t) for t in ts]
    ys = [yC + R*math.sin(t) for t in ts]
    return xs, ys

@app.route("/plot")
def plot():
    a   = parse_float(request.args, "a", 1.0)
    b   = parse_float(request.args, "b", 1.5)
    lam = parse_float(request.args, "lam", 3.0)
    zD  = parse_float(request.args, "zD", 0.75)
    wE  = parse_float(request.args, "wE", 0.9)
    tL  = parse_float(request.args, "tL", 0.03)
    Rf  = parse_float(request.args, "Rf", 0.2)

    left, right = compute_both(a,b,lam,zD,wE,tL,Rf)
    Lp = dict(left["points"]); Rp = dict(right["points"])
    La = {n:d for n,d in left["arcs"]}; Ra = {n:d for n,d in right["arcs"]}

    fig, ax = plt.subplots(figsize=(7,6), dpi=140)

    # helper to draw one side
    def draw_side(P, A, color=None):
        def draw_arc(name, p0, p1):
            xs, ys = arc_points((A[name]['Cx'], A[name]['Cy']), A[name]['R'], P[p0], P[p1])
            ax.plot(xs, ys, lw=2, color=color)
        draw_arc('AF','A','F')
        draw_arc('FG','F','G')
        draw_arc('HI1','H','I1')
        draw_arc('I1I2','I1','I2')
        draw_arc('I2D','I2','D')
        draw_arc('DE','D','E')

    draw_side(Lp, La, color=None)
    draw_side(Rp, Ra, color=None)

    # draw HG segments
    for side in (left, right):
        for name, S in side["segments"]:
            if name=="HG":
                ax.plot([S["x0"], S["x1"]], [S["y0"], S["y1"]], lw=2)

    # draw and label points
    for name,(x,y) in left["points"] + right["points"]:
        ax.plot(x,y,'ko',ms=3)
        ax.text(x+0.03*max(1,a), y+0.03*max(1,lam/3), name, fontsize=8, weight='bold')

    ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
    ax.set_xlabel('x'); ax.set_ylabel('y (axial)')
    xs_all = [p[0] for _,p in left["points"]+right["points"]]; ys_all = [p[1] for _,p in left["points"]+right["points"]]
    pad = 0.4*max(1,a)
    ax.set_xlim(min(xs_all)-pad, max(xs_all)+pad)
    ax.set_ylim(-0.2*lam, lam+0.2*lam)
    fig.tight_layout()

    buf = io.BytesIO(); fig.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

@app.route("/", methods=["GET", "POST"])
def index():
    defaults = dict(a=1.0, b=1.5, lam=3.0, zD=0.75, wE=0.9, tL=0.03, Rf=0.2)
    error = None
    if request.method == "POST":
        try:
            a   = float(request.form["a"]); b   = float(request.form["b"])
            lam = float(request.form["lam"]); zD  = float(request.form["zD"])
            wE  = float(request.form["wE"]); tL  = float(request.form["tL"])
            Rf  = float(request.form["Rf"])
            left, right = compute_both(a,b,lam,zD,wE,tL,Rf)
            return render_template_string(PAGE, defaults=defaults, error=None,
                    results={"inputs": dict(a=a,b=b,lam=lam,zD=zD,wE=wE,tL=tL,Rf=Rf),
                             "left": left, "right": right})
        except Exception as e:
            error = str(e)
            return render_template_string(PAGE, defaults=defaults, error=error, results=None)
    else:
        return render_template_string(PAGE, defaults=defaults, error=None, results=None)

if __name__ == "__main__":
    app.run(debug=True)
