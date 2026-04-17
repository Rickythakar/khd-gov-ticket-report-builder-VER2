import re

with open("templates/dashboard.html", "r") as f:
    content = f.read()

# Replace the panel-preview and panel-body in TRENDS section
old_trends_regex = r'<div class="panel span-2 fade fd2" style="margin-bottom:12px; grid-column: 1 / -1;">.*?</div>\s*</div>\s*</div>\s*</div>'

new_trends_html = r"""<div class="panel span-2 fade fd2" style="margin-bottom:12px; grid-column: 1 / -1;">
      <div class="panel-trigger" onclick="togglePanel(this, event)">
        <div class="panel-head">
          <div class="p-title"><span class="dot" style="background:var(--blue);"></span>Trend Vectors</div>
          <div class="p-meta">{{ comp.month_count }} MONTHS <span class="p-arrow">►</span></div>
        </div>
        <div class="panel-preview" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
          <!-- Volume -->
          <div style="border-left: 2px solid var(--cyan); padding-left: 12px; background: rgba(0, 229, 255, 0.03); padding-top: 6px; padding-bottom: 6px;">
            <div class="pv-lbl">VOLUME</div>
            <div style="display:flex; align-items:baseline; gap: 8px; margin-top: 4px;">
              <span style="font-size:16px; color:var(--text); font-weight:300;">{{ comp.trends.tickets[0] }}</span>
              <span style="font-size:10px; color:var(--dim);">→</span>
              <span style="font-size:16px; color:var(--cyan); font-weight:600;">{{ comp.trends.tickets[-1] }}</span>
            </div>
            <div style="font-size:8px; color:var(--dim); margin-top:4px;">{{ comp.trends.labels[0] }} TO {{ comp.trends.labels[-1] }}</div>
          </div>
          <!-- SLA -->
          <div style="border-left: 2px solid var(--green); padding-left: 12px; background: rgba(0, 250, 154, 0.03); padding-top: 6px; padding-bottom: 6px;">
            <div class="pv-lbl">SLA COMPLIANCE</div>
            <div style="display:flex; align-items:baseline; gap: 8px; margin-top: 4px;">
              <span style="font-size:16px; color:var(--text); font-weight:300;">{{ comp.trends.sla_compliance[0] }}%</span>
              <span style="font-size:10px; color:var(--dim);">→</span>
              <span style="font-size:16px; color:var(--green); font-weight:600;">{{ comp.trends.sla_compliance[-1] }}%</span>
            </div>
            <div style="font-size:8px; color:var(--dim); margin-top:4px;">{{ comp.trends.labels[0] }} TO {{ comp.trends.labels[-1] }}</div>
          </div>
          <!-- Escalation -->
          <div style="border-left: 2px solid var(--amber); padding-left: 12px; background: rgba(255, 184, 0, 0.03); padding-top: 6px; padding-bottom: 6px;">
            <div class="pv-lbl">ESCALATION RATE</div>
            <div style="display:flex; align-items:baseline; gap: 8px; margin-top: 4px;">
              <span style="font-size:16px; color:var(--text); font-weight:300;">{{ comp.trends.escalation_rate[0] }}%</span>
              <span style="font-size:10px; color:var(--dim);">→</span>
              <span style="font-size:16px; color:var(--amber); font-weight:600;">{{ comp.trends.escalation_rate[-1] }}%</span>
            </div>
            <div style="font-size:8px; color:var(--dim); margin-top:4px;">{{ comp.trends.labels[0] }} TO {{ comp.trends.labels[-1] }}</div>
          </div>
          <!-- Resolution -->
          <div style="border-left: 2px solid var(--blue); padding-left: 12px; background: rgba(0, 102, 255, 0.03); padding-top: 6px; padding-bottom: 6px;">
            <div class="pv-lbl">MEDIAN RES.</div>
            <div style="display:flex; align-items:baseline; gap: 8px; margin-top: 4px;">
              <span style="font-size:16px; color:var(--text); font-weight:300;">{{ comp.trends.median_resolution[0] }}m</span>
              <span style="font-size:10px; color:var(--dim);">→</span>
              <span style="font-size:16px; color:var(--blue); font-weight:600;">{{ comp.trends.median_resolution[-1] }}m</span>
            </div>
            <div style="font-size:8px; color:var(--dim); margin-top:4px;">{{ comp.trends.labels[0] }} TO {{ comp.trends.labels[-1] }}</div>
          </div>
        </div>
      </div>
      <div class="panel-body-wrap">
        <div class="panel-body">
          <div class="ascii-loader"></div>
          <div class="panel-content">
            <script>window.TREND_DATA = {{ comp.trends | tojson }};</script>
            <div class="c2" style="margin-bottom: 24px;">
              <!-- 2x2 Grid of SVG Graphs -->
              <div style="border: 1px solid var(--border); background: var(--bg); padding: 16px; position:relative;">
                <div class="pv-lbl" style="color:var(--cyan); margin-bottom:12px;">VOLUME TREND</div>
                <svg class="trend-chart" data-key="tickets" data-color="var(--cyan)" data-unit="" width="100%" height="140" style="display:block;"></svg>
              </div>
              <div style="border: 1px solid var(--border); background: var(--bg); padding: 16px; position:relative;">
                <div class="pv-lbl" style="color:var(--green); margin-bottom:12px;">SLA COMPLIANCE</div>
                <svg class="trend-chart" data-key="sla_compliance" data-color="var(--green)" data-unit="%" width="100%" height="140" style="display:block;"></svg>
              </div>
              <div style="border: 1px solid var(--border); background: var(--bg); padding: 16px; position:relative;">
                <div class="pv-lbl" style="color:var(--amber); margin-bottom:12px;">ESCALATION RATE</div>
                <svg class="trend-chart" data-key="escalation_rate" data-color="var(--amber)" data-unit="%" width="100%" height="140" style="display:block;"></svg>
              </div>
              <div style="border: 1px solid var(--border); background: var(--bg); padding: 16px; position:relative;">
                <div class="pv-lbl" style="color:var(--blue); margin-bottom:12px;">MEDIAN RESOLUTION</div>
                <svg class="trend-chart" data-key="median_resolution" data-color="var(--blue)" data-unit="m" width="100%" height="140" style="display:block;"></svg>
              </div>
            </div>
            
            <div class="tab-bar">
              <button class="tab-btn on" style="cursor:default; border-bottom-color:var(--cyan);">Historical Ledger</button>
            </div>
            <div class="tab-panel on" data-tabs="trends">
              <table class="tbl">
                <tr><th>Month</th><th class="r">Tickets</th><th class="r">Esc%</th><th class="r">SLA%</th><th class="r">Med Res</th><th class="r">FCR%</th></tr>
                {% for m in comp.months %}
                <tr>
                  <td><span style="color:var(--bright);">{{ m.label }}</span></td>
                  <td class="r">{{ m.tickets }}</td>
                  <td class="r">{{ m.escalation_rate }}%</td>
                  <td class="r {% if m.sla >= 90 %}accent{% elif m.sla < 80 %}bad-text{% endif %}">{{ m.sla }}%</td>
                  <td class="r">{{ m.median_res_fmt }}</td>
                  <td class="r">{{ m.fcr }}%</td>
                </tr>
                {% endfor %}
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>"""

content = re.sub(old_trends_regex, new_trends_html, content, flags=re.DOTALL)

with open("templates/dashboard.html", "w") as f:
    f.write(content)

print("Patch Trends successful.")
