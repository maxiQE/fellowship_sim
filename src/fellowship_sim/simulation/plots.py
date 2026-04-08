import html as _html
import json
import pathlib
import tempfile
import webbrowser

import plotly.graph_objects as go

from fellowship_sim.simulation.metrics import DEFAULT_METRICS, MeanStd, Metric, ScalarMetric
from fellowship_sim.simulation.runner import RepetitionResult

_PALETTE = ["#003f5c", "#f95d6a", "#665191", "#ffa600", "#d45087", "#2f4b7c", "#ff7c43", "#a05195"]


def _color_map(metrics: list[Metric]) -> dict[str, str]:
    return {m.name: _PALETTE[i % len(_PALETTE)] for i, m in enumerate(metrics)}



def scenario_figure(
    all_results: dict[tuple[str, str, str], RepetitionResult],
    scenario_name: str,
    setup_names: list[str],
    rotation_names: list[str],
    metrics: list[Metric] = DEFAULT_METRICS,
) -> go.Figure:
    """Bar chart for a single scenario.

    X axis: one position per (setup, rotation) pair, labeled "{setup}\\n{rotation}".
    Y axis: each value normalized to the first (setup, rotation) pair for that metric.
    Color: metric name.

    Each trace carries meta={"setup": ..., "rotation": ...} so the toggle JS can
    show/hide traces without knowing their index or order.
    Metrics with show_on_st=False are omitted when the scenario is single-target.
    """
    pairs: list[tuple[str, str]] = [(s, r) for s in setup_names for r in rotation_names]
    ref_setup, ref_rotation = pairs[0]
    pair_labels: list[str] = [f"{s}\n{r}" for s, r in pairs]

    ref_result = all_results[(scenario_name, ref_setup, ref_rotation)].metrics
    is_st = ref_result.is_single_target

    scalar_metrics = [m for m in metrics if isinstance(m, ScalarMetric)]
    visible_metrics = [m for m in scalar_metrics if m.show_on_st or not is_st]
    colors = _color_map(metrics=metrics)

    fig = go.Figure()
    metric_legend_shown: set[str] = set()

    for metric_idx, metric in enumerate(visible_metrics):
        ref_mean: float = ref_result.scalars[metric.name].mean
        ref = ref_mean if ref_mean != 0.0 else 1.0

        for setup_name, rotation_name in pairs:
            ms: MeanStd = all_results[(scenario_name, setup_name, rotation_name)].metrics.scalars[metric.name]
            show_in_legend = metric.name not in metric_legend_shown
            if show_in_legend:
                metric_legend_shown.add(metric.name)
            ratio = ms.mean / ref
            pct = (ratio - 1.0) * 100.0
            fig.add_trace(go.Bar(
                name=metric.name,
                x=[f"{setup_name}\n{rotation_name}"],
                y=[ratio],
                error_y={"type": "data", "array": [ms.stderr / ref], "visible": True},
                customdata=[[f"{ms.mean:,.1f} ± {ms.stderr:,.1f}", f"{pct:+.1f}%"]],
                hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra>%{fullData.name}</extra>",
                legendgroup=metric.name,
                showlegend=show_in_legend,
                marker_color=colors[metric.name],
                offsetgroup=str(metric_idx),
                meta={"setup": setup_name, "rotation": rotation_name},
            ))

    fig.update_xaxes(categoryorder="array", categoryarray=pair_labels)
    fig.update_layout(
        barmode="group",
        bargap=0.2,
        bargroupgap=0.0,
        yaxis_title="relative to first pair",
        title=scenario_name,
    )
    return fig


def grouped_figure(
    all_results: dict[tuple[str, str, str], RepetitionResult],
    scenario_names: list[str],
    setup_names: list[str],
    rotation_names: list[str],
    metrics: list[Metric] = DEFAULT_METRICS,
) -> go.Figure:
    """Bar chart for all scenarios combined into a single figure.

    X axis: one position per (scenario, setup, rotation) triple, labeled
    "{scenario}\\n{setup}\\n{rotation}".
    Y axis: all values normalized to the first (scenario, setup, rotation) triple
    globally — so bars across different scenarios are directly comparable.
    Color: metric name.

    Each trace carries meta={"scenario": ..., "setup": ..., "rotation": ...} so
    all three axes can be toggled independently in the browser.
    Metric suppression is evaluated against the first scenario's first pair.
    """
    pairs: list[tuple[str, str]] = [(s, r) for s in setup_names for r in rotation_names]
    ref_setup, ref_rotation = pairs[0]
    ref_scenario = scenario_names[0]

    ref_result = all_results[(ref_scenario, ref_setup, ref_rotation)].metrics
    is_st = ref_result.is_single_target

    scalar_metrics = [m for m in metrics if isinstance(m, ScalarMetric)]
    visible_metrics = [m for m in scalar_metrics if m.show_on_st or not is_st]
    colors = _color_map(metrics=metrics)

    fig = go.Figure()
    metric_legend_shown: set[str] = set()

    for scenario_name in scenario_names:
        for metric_idx, metric in enumerate(visible_metrics):
            ref_mean: float = all_results[(ref_scenario, ref_setup, ref_rotation)].metrics.scalars[metric.name].mean
            ref = ref_mean if ref_mean != 0.0 else 1.0

            for setup_name, rotation_name in pairs:
                ms: MeanStd = all_results[(scenario_name, setup_name, rotation_name)].metrics.scalars[metric.name]
                show_in_legend = metric.name not in metric_legend_shown
                if show_in_legend:
                    metric_legend_shown.add(metric.name)
                fig.add_trace(go.Bar(
                    name=metric.name,
                    x=[f"{scenario_name}\n{setup_name}\n{rotation_name}"],
                    y=[ms.mean / ref],
                    error_y={"type": "data", "array": [ms.stderr / ref], "visible": True},
                    customdata=[[f"{ms.mean:,.1f} ± {ms.stderr:,.1f}", f"{(ms.mean / ref - 1.0) * 100.0:+.1f}%"]],
                    hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra>%{fullData.name}</extra>",
                    legendgroup=metric.name,
                    showlegend=show_in_legend,
                    marker_color=colors[metric.name],
                    offsetgroup=str(metric_idx),
                    meta={"scenario": scenario_name, "setup": setup_name, "rotation": rotation_name},
                ))

    triple_labels: list[str] = [
        f"{scenario}\n{setup}\n{rotation}"
        for scenario in scenario_names
        for setup, rotation in pairs
    ]
    fig.update_xaxes(categoryorder="array", categoryarray=triple_labels)
    fig.update_layout(
        barmode="group",
        bargap=0.2,
        bargroupgap=0.0,
        yaxis_title="relative to first pair (per scenario)",
    )
    return fig


def _build_html(
    plotly_html: str,
    axes: list[tuple[str, list[str], str]],
    orig_x_labels: list[str],
) -> str:
    """Wrap a Plotly HTML snippet with toggle-button rows.

    axes: one entry per button row — (display_label, names, meta_key).
        display_label is shown as the row heading.
        names are the button labels, one button each.
        meta_key is the key to look up on trace.meta in the JS filter.
    orig_x_labels: the complete ordered x-axis category array.  Stored in JS so
        the categoryarray can be narrowed to only active labels on each toggle
        (Plotly otherwise keeps phantom empty slots for hidden traces).

    The generated JS filters traces by checking every axis's meta_key against the
    active set for that axis.  No index arithmetic — each trace is matched solely
    by its meta dict.
    """
    axes_json = json.dumps([
        {"label": label, "key": key, "names": names}
        for label, names, key in axes
    ])
    orig_x_json = json.dumps(orig_x_labels)

    button_rows = ""
    for row_idx, (label, names, _key) in enumerate(axes):
        buttons = "".join(
            f'<button id="btn-{row_idx}-{i}" class="toggle-btn active" '
            f'onclick="toggle({row_idx},{i},this)">'
            f"{_html.escape(name)}</button>"
            for i, name in enumerate(names)
        )
        button_rows += (
            f'<div class="control-row">'
            f'<span class="control-label">{_html.escape(label)}</span>'
            f"{buttons}</div>\n"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: sans-serif; margin: 20px; }}
    .control-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
    .control-label {{ font-weight: bold; min-width: 80px; color: #444; }}
    .toggle-btn {{
      padding: 5px 14px;
      border: 1px solid #999;
      border-radius: 4px;
      cursor: pointer;
      background: #e0e0e0;
      color: #333;
      font-size: 13px;
      transition: background 0.15s, border-color 0.15s;
    }}
    .toggle-btn.active {{
      background: #90EE90;
      border-color: #4CAF50;
      color: #1a1a1a;
    }}
    .toggle-btn:hover {{ filter: brightness(0.95); }}
  </style>
</head>
<body>
  {button_rows}
  {plotly_html}
  <script>
  var AXES = {axes_json};
  var ORIG_X_LABELS = {orig_x_json};
  var active = {{}};
  AXES.forEach(function(ax) {{
    active[ax.key] = {{}};
    ax.names.forEach(function(n) {{ active[ax.key][n] = true; }});
  }});

  function toggle(rowIdx, nameIdx, btnEl) {{
    var ax = AXES[rowIdx];
    var name = ax.names[nameIdx];
    active[ax.key][name] = !active[ax.key][name];
    btnEl.classList.toggle('active', active[ax.key][name]);
    update();
  }}

  function update() {{
    var gd = document.getElementById('main-plot');
    var vis = gd.data.map(function(trace) {{
      if (!trace.meta) return true;
      return AXES.every(function(ax) {{
        var val = trace.meta[ax.key];
        return val === undefined || active[ax.key][val];
      }});
    }});
    var visSet = {{}};
    gd.data.forEach(function(trace, i) {{
      if (vis[i] && trace.x) {{
        trace.x.forEach(function(lbl) {{ visSet[lbl] = true; }});
      }}
    }});
    var activeLabels = ORIG_X_LABELS.filter(function(l) {{ return visSet[l]; }});
    Plotly.restyle(gd, {{visible: vis}});
    Plotly.relayout(gd, {{'xaxis.categoryarray': activeLabels}});
  }}
  </script>
</body>
</html>"""


def _open_html(page: str) -> None:
    """Write an HTML string to a temporary file and open it in the default browser."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(page)
        tmp_path = f.name
    webbrowser.open(pathlib.Path(tmp_path).as_uri())


def show_comparison(
    all_results: dict[tuple[str, str, str], RepetitionResult],
    scenario_names: list[str],
    setup_names: list[str],
    rotation_names: list[str],
    metrics: list[Metric] = DEFAULT_METRICS,
) -> None:
    """Open one browser tab per scenario, each showing a bar chart for that scenario.

    Each tab has Setup and Rotation toggle buttons.  Bars are normalized to the
    first (setup, rotation) pair.  Metrics with show_on_st=False are omitted for
    single-target scenarios.
    """
    pairs: list[tuple[str, str]] = [(s, r) for s in setup_names for r in rotation_names]
    pair_labels: list[str] = [f"{s}\n{r}" for s, r in pairs]
    axes: list[tuple[str, list[str], str]] = [
        ("Setups", setup_names, "setup"),
        ("Rotations", rotation_names, "rotation"),
    ]
    for scenario_name in scenario_names:
        fig = scenario_figure(
            all_results=all_results,
            scenario_name=scenario_name,
            setup_names=setup_names,
            rotation_names=rotation_names,
            metrics=metrics,
        )
        plotly_html = fig.to_html(include_plotlyjs="cdn", full_html=False, div_id="main-plot")
        _open_html(_build_html(plotly_html=plotly_html, axes=axes, orig_x_labels=pair_labels))


def show_grouped_comparison(
    all_results: dict[tuple[str, str, str], RepetitionResult],
    scenario_names: list[str],
    setup_names: list[str],
    rotation_names: list[str],
    metrics: list[Metric] = DEFAULT_METRICS,
) -> None:
    """Open one browser tab showing all scenarios, setups, and rotations in a single figure.

    Each (scenario, setup, rotation) triple is its own bar group on the x axis.
    Three rows of toggle buttons — Scenarios, Setups, Rotations — let any axis be
    filtered independently.  Bars are normalized per-scenario to the first
    (setup, rotation) pair within that scenario.
    """
    pairs: list[tuple[str, str]] = [(s, r) for s in setup_names for r in rotation_names]
    triple_labels: list[str] = [
        f"{scenario}\n{setup}\n{rotation}"
        for scenario in scenario_names
        for setup, rotation in pairs
    ]
    axes: list[tuple[str, list[str], str]] = [
        ("Scenarios", scenario_names, "scenario"),
        ("Setups", setup_names, "setup"),
        ("Rotations", rotation_names, "rotation"),
    ]
    fig = grouped_figure(
        all_results=all_results,
        scenario_names=scenario_names,
        setup_names=setup_names,
        rotation_names=rotation_names,
        metrics=metrics,
    )
    plotly_html = fig.to_html(include_plotlyjs="cdn", full_html=False, div_id="main-plot")
    _open_html(_build_html(plotly_html=plotly_html, axes=axes, orig_x_labels=triple_labels))
