const navigation = ["Overview", "Sites", "Chargers", "Sessions", "Billing"];

const metrics = [
  { label: "Connected chargers", value: "1,846", detail: "92.3% of seed fleet" },
  { label: "Active sessions", value: "312", detail: "+24 in the last hour" },
  { label: "Telemetry rate", value: "198", unit: "msg/s", detail: "Synthetic baseline" },
  { label: "Authorization p95", value: "184", unit: "ms", detail: "UI seed value" },
];

const sites = [
  { name: "North Ring Hub", tenant: "Voltline", load: 82, active: 46, limit: "420 kW" },
  { name: "Canal Market", tenant: "CityCharge", load: 64, active: 31, limit: "280 kW" },
  { name: "M2 Service Plaza", tenant: "RoadSpark", load: 39, active: 18, limit: "500 kW" },
];

const hourlyLoad = [31, 35, 33, 38, 46, 57, 68, 72, 63, 75, 82, 71];

function App() {
  return (
    <div className="console-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">
            H
          </span>
          <div>
            <strong>H.E.R.B.I.E.</strong>
            <span>Network control</span>
          </div>
        </div>

        <nav aria-label="Primary navigation">
          {navigation.map((item, index) => (
            <button className={index === 0 ? "nav-item active" : "nav-item"} key={item}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className="pulse-dot" aria-hidden="true" />
          <div>
            <strong>Simulation online</strong>
            <span>Foundation environment</span>
          </div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">Operator workspace / Demo tenant</p>
            <h1>Charging operations</h1>
          </div>
          <div className="topbar-actions">
            <span className="seed-badge">Synthetic snapshot</span>
            <button className="outline-button" type="button">
              View evidence
            </button>
          </div>
        </header>

        <section className="grid-summary" aria-label="Synthetic platform summary">
          {metrics.map((metric) => (
            <article className="metric-card" key={metric.label}>
              <span>{metric.label}</span>
              <div>
                <strong>{metric.value}</strong>
                {metric.unit ? <small>{metric.unit}</small> : null}
              </div>
              <p>{metric.detail}</p>
            </article>
          ))}
        </section>

        <section className="operations-grid">
          <article className="panel load-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Aggregate site demand</p>
                <h2>Load envelope</h2>
              </div>
              <div className="load-total">
                <strong>682</strong>
                <span>kW / 1.2 MW</span>
              </div>
            </div>

            <div className="bar-chart" aria-label="Synthetic twelve-hour load chart">
              {hourlyLoad.map((height, index) => (
                <div className="bar-slot" key={`${height}-${index}`}>
                  <span style={{ height: `${height}%` }} />
                </div>
              ))}
            </div>
            <div className="chart-scale">
              <span>08:00</span>
              <span>14:00</span>
              <span>20:00</span>
            </div>
          </article>

          <article className="panel tenant-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Isolation view</p>
                <h2>Tenant lanes</h2>
              </div>
              <span className="healthy-label">3 healthy</span>
            </div>
            <div className="tenant-lanes">
              <div>
                <span className="tenant-code orange">VL</span>
                <p><strong>Voltline</strong><small>914 chargers</small></p>
                <em>99.7%</em>
              </div>
              <div>
                <span className="tenant-code teal">CC</span>
                <p><strong>CityCharge</strong><small>603 chargers</small></p>
                <em>99.9%</em>
              </div>
              <div>
                <span className="tenant-code sand">RS</span>
                <p><strong>RoadSpark</strong><small>483 chargers</small></p>
                <em>99.5%</em>
              </div>
            </div>
            <p className="data-note">Percentages are interface seed data, not measured availability.</p>
          </article>
        </section>

        <section className="panel sites-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Power allocation</p>
              <h2>Sites nearest limit</h2>
            </div>
            <button className="text-button" type="button">Open all sites</button>
          </div>

          <div className="site-list">
            {sites.map((site) => (
              <article key={site.name}>
                <div className="site-name">
                  <strong>{site.name}</strong>
                  <span>{site.tenant}</span>
                </div>
                <div className="capacity-track" aria-label={`${site.load}% of site limit`}>
                  <span style={{ width: `${site.load}%` }} />
                </div>
                <div className="site-stat">
                  <strong>{site.load}%</strong>
                  <span>{site.active} sessions / {site.limit}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <footer>
          <span>H.E.R.B.I.E. / SE 315 Cloud Computing</span>
          <span>All values on this screen are deterministic demo fixtures.</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
