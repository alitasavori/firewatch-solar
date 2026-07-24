import { useState, useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';
import { API_BASE } from '../config';
import '../styles/InfoPanel.css';

const ELECTRICITY_RATE_PER_KWH = 0.12;
const KWH_PER_MWH = 1000;

const BarChart = ({ data }) => {
    //const svgRef = useRef();
    const containerRef = useRef(null);

    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        function draw() {
            const W = container.clientWidth;
            const H = container.clientHeight;

            const margin = { top: 20, right: 20, bottom: 80, left: 70 },
                width = W - margin.left - margin.right,
                height = H - margin.top - margin.bottom;

            d3.select(container).selectAll("*").remove();

            const svg = d3.select(container)
                .append("svg")
                .attr("width", W) //width + margin.left + margin.right)
                .attr("height", H) //height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", `translate(${margin.left},${margin.top})`);

            const xScale = d3.scaleBand()
                .domain(data.map(d => d.date))
                .range([0, width])
                .padding(0.1);

            const yScale = d3.scaleLinear()
                .domain([0, d3.max(data, d => d.baseline) * 1.1])
                .nice()
                .range([height, 0]);

            const xAxis = d3.axisBottom(xScale)
                .tickFormat(d => {
                    const [year, month, day] = d.split("-");
                    return `${month}/${day}`;
                });

            const yAxis = d3.axisLeft(yScale)
                .ticks(5);

            const yGrid = d3.axisLeft(yScale)
                .tickFormat("")
                .tickSize(-width)
                .ticks(5);

            const subgroups = ["baseline", "lstm_pred"];
            const xSubgroup = d3.scaleBand()
                .domain(subgroups)
                .range([0, xScale.bandwidth()])
                .padding(0.15);

            const keyLabels = {
                baseline: "No Wildfires",
                lstm_pred: "With Wildfires"
            };

            const axisInk = "#c8d4e6";
            const labelInk = "#e8eef5";

            const xAxisG = svg.append("g")
                .attr("transform", `translate(0,${height})`)
                .call(xAxis);
            xAxisG.selectAll("text")
                .style("text-anchor", "end")
                .attr("dx", "-.8em")
                .attr("dy", ".15em")
                .attr("transform", "rotate(-65)")
                .attr("fill", axisInk);
            xAxisG.selectAll("line, path").attr("stroke", axisInk);

            const yAxisG = svg.append("g").call(yAxis);
            yAxisG.selectAll("text").attr("fill", axisInk);
            yAxisG.selectAll("line, path").attr("stroke", axisInk);

            svg.append("g")
                .attr('class', 'y-grid')
                .attr("stroke-opacity", 0.15)
                .call(yGrid)
                .selectAll("line")
                .attr("stroke", "#8fa3c7");

            const tooltip = d3.select("body")
                .append("div")
                .style("position", "absolute")
                .style("padding", "6px 10px")
                .style("background", "rgba(0,0,0,0.75)")
                .style("color", "white")
                .style("border-radius", "4px")
                .style("pointer-events", "none")
                .style("opacity", 0)
                .style("font-size", "13px");

            svg.append("g")
                .selectAll("g")
                .data(data)
                .enter().append("g")
                .attr("transform", d => `translate(${xScale(d.date)},0)`)
                .selectAll("rect")
                .data(d => subgroups.map(key => ({
                    key,
                    value: d[key] != null ? d[key] : 0,
                    day: d.date
                })))
                .enter().append("rect")
                .attr("x", d => xSubgroup(d.key))
                .attr("y", d => yScale(d.value))
                .attr("width", xSubgroup.bandwidth())
                .attr("height", d => yScale(0) - yScale(d.value))
                .attr("fill", d => d.key === "lstm_pred" ? "orange" : "steelblue")
                .on("mouseover", function (event, d) {
                    tooltip.style("opacity", 1);
                    d3.select(this).attr("opacity", 0.7); // highlight
                })
                .on("mousemove", function (event, d) {

                    // Convert "YYYY-MM-DD" → "MM/DD/YYYY"
                    const [year, month, day] = d.day.split("-");
                    const niceDate = `${month}/${day}/${year}`;

                    tooltip
                        .html(`
                <strong>${keyLabels[d.key] || d.key}</strong><br>
                Date: <strong>${niceDate}</strong><br>
                Value: <strong>${d.value.toFixed(2)}</strong>
            `)
                        .style("top", (event.pageY - 40) + "px")
                        .style("left", (event.pageX + 10) + "px");
                })

                .on("mouseout", function () {
                    tooltip.style("opacity", 0);
                    d3.select(this).attr("opacity", 1); // reset color
                });

            svg.selectAll(".xlabel")
                .data([null])
                .join("text")
                .attr("class", "xlabel")
                .attr("x", width / 2)
                .attr("y", height + margin.bottom - 20)
                .attr("text-anchor", "middle")
                .attr("fill", labelInk)
                .style("font-size", 20)
                .style("font-family", "helvetica")
                .text("Date");

            svg.selectAll(".ylabel")
                .data([null])
                .join("text")
                .attr("class", "ylabel")
                .attr("x", -height / 2)
                .attr("y", -margin.left / 2)
                .attr("text-anchor", "middle")
                .attr("transform", "rotate(-90)")
                .attr("fill", labelInk)
                .style("font-size", 20)
                .style("font-family", "helvetica")
                .style("-webkit-font-smoothing", "antialiased")
                .style("-moz-osx-font-smoothing", "grayscale")
                .text("PV Output (MWh)");

            // Legend data
            const legend = [
                { label: "No Wildfires", color: "steelblue" },
                { label: "With Wildfires", color: "orange" }
            ];

            // Legend group container
            const legendGroup = svg.append("g")
                //.attr("transform", `translate(${width - 150}, ${margin.top})`);
                .attr("transform", `translate(${width / 2 - margin.left - margin.right}, ${-margin.top / 2 - 5})`);

            // Legend items
            legendGroup.selectAll("legend-item")
                .data(legend)
                .enter().append("g")
                .attr("class", "legend-item")
                .attr("transform", (d, i) => `translate(${i * (margin.left + margin.right + 20)}, 0)`)//`translate(10, ${i * 20 + 10})`)
                .each(function (d) {
                    const g = d3.select(this);
                    // Color box
                    g.append("rect")
                        .attr("width", 14)
                        .attr("height", 14)
                        .attr("fill", d.color);
                    // Label
                    g.append("text")
                        .attr("x", 20)
                        .attr("y", 12)
                        .attr("fill", labelInk)
                        .text(d.label)
                        .style("font-size", "13");
                });
        }

        draw();

        const resizeObserver = new ResizeObserver(draw);
        resizeObserver.observe(container);

        return () => {
            resizeObserver.disconnect();
            d3.select(container).selectAll("*").remove();
        };

    }, [data]);//, [data]);

    return (
        <div
            ref={containerRef}
            style={{
                width: "100%",
                height: "30vh",
                minHeight: "180px",
                position: "relative",
            }}
        ></div>
    );
};

const SRITrend = ({ sriData, selectedDayIndex, onSelectDay }) => {
    const [hoverInfo, setHoverInfo] = useState(null);

    if (!sriData || sriData.length === 0) {
        return <div>Loading SRI trend...</div>;
    }

    // Sparkline logic
    const sriValues = sriData.map((d) => d.SRI);

    const width = 200;
    const height = 70;
    const padding = 6;

    const xScale = (i) =>
        padding + (i / (sriValues.length - 1)) * (width - 2 * padding);

    const minSRI = Math.min(...sriValues);
    const maxSRI = Math.max(...sriValues);

    const yScale = (v) =>
        padding +
        (1 - (v - minSRI) / (maxSRI - minSRI + 1e-9)) * (height - 2 * padding);

    // Line points
    const linePoints = sriValues
        .map((v, i) => `${xScale(i)},${yScale(v)}`)
        .join(" ");

    // Area fill
    const areaPoints =
        `${xScale(0)},${height - padding} ` +
        linePoints +
        ` ${xScale(sriValues.length - 1)},${height - padding}`;

    // Tooltip width & height
    const tooltipWidth = 68;
    const tooltipHeight = 15;

    return (
        <svg width={width} height={height} style={{ overflow: "visible" }}>
            {/* Area Fill */}
            <polygon
                points={areaPoints}
                fill="rgba(0, 116, 217, 0.10)"
            />

            {/* Trend Line */}
            <polyline
                fill="none"
                stroke="#0074D9"
                strokeWidth="2"
                points={linePoints}
            />

            {/* Dots */}
            {sriValues.map((v, i) => (
                <circle
                    key={i}
                    cx={xScale(i)}
                    cy={yScale(v)}
                    r={i === selectedDayIndex ? 4 : 3}
                    fill={i === selectedDayIndex ? "red" : "#0074D9"}
                    cursor="pointer"

                    onClick={() => onSelectDay(i)}

                    onMouseEnter={() =>
                        setHoverInfo({
                            x: xScale(i),
                            y: yScale(v),
                            sri: `SRI: ${(v * 100).toFixed(2)}%`,
                        })
                    }
                    onMouseLeave={() => setHoverInfo(null)}
                />
            ))}

            {/* Tooltip (SVG-based, does NOT overflow or clip) */}
            {hoverInfo && (
                <g>
                    {/* Auto-adjust X so tooltip never leaves the SVG */}
                    <rect
                        x={Math.min(
                            hoverInfo.x + 8,
                            width - tooltipWidth - 5
                        )}
                        y={hoverInfo.y - tooltipHeight - 6}
                        width={tooltipWidth}
                        height={tooltipHeight}
                        fill="rgba(0,0,0,0.75)"
                        stroke="rgba(255,255,255,0.35)"
                        rx="4"
                    />
                    <text
                        x={Math.min(
                            hoverInfo.x + 10,
                            width - tooltipWidth
                        )}
                        y={hoverInfo.y - tooltipHeight / 2}
                        fontSize="11"
                        fill="white"
                        style={{ fontFamily: "sans-serif" }}
                    >
                        {hoverInfo.sri}
                    </text>
                </g>
            )}
        </svg>
    );
};

const SRIGauge = ({ value }) => {
    const wrapperRef = useRef(null);
    const [size, setSize] = useState({ width: 260, height: 160 });

    useEffect(() => {
        const elem = wrapperRef.current;
        if (!elem) return;

        const ro = new ResizeObserver(entries => {
            const { width, height } = entries[0].contentRect;
            setSize({ width, height });
        });

        ro.observe(elem);

        return () => ro.disconnect();
    }, []); // run once

    if (value == null) return null;

    const { width, height } = size;

    const sriPercent = value * 100;

    let instruction = "";
    if (sriPercent >= 99.0) instruction = "instruction: All Good";
    else if (sriPercent >= 98.0) instruction = "instruction: Check Panels";
    else instruction = "instruction: Urgent Cleaning";

    // Geometry
    const cx = width / 2;
    const cy = height * 0.82; // bottom offset adaptively
    const radius = Math.min(width, height) * 0.45;

    let angle = (sriPercent - 97) * 60;
    angle = Math.max(0, Math.min(180, angle));

    const rad = (angle * Math.PI) / 180;
    const needleLen = radius * 0.75;

    const needleX = cx + needleLen * Math.cos(rad);
    const needleY = cy - needleLen * Math.sin(rad);

    const arc = (start, end, color) => {
        const startRad = (start * Math.PI) / 180;
        const endRad = (end * Math.PI) / 180;

        const x1 = cx + radius * Math.cos(startRad);
        const y1 = cy - radius * Math.sin(startRad);

        const x2 = cx + radius * Math.cos(endRad);
        const y2 = cy - radius * Math.sin(endRad);

        return (
            <path
                d={`M ${x1} ${y1} A ${radius} ${radius} 0 0 0 ${x2} ${y2}`}
                stroke={color}
                strokeWidth={radius * 0.19}
                fill="none"
                strokeLinecap="butt"
            />
        );
    };

    return (
        <div
            ref={wrapperRef}
            style={{
                width: "100%",
                height: "25vh",
                minHeight: "150px",
                position: "relative",
            }}
        >
            <svg width={width} height={height}>
                {arc(0, 60, "#e74c3c")}
                {arc(60, 120, "#f1c40f")}
                {arc(120, 180, "#2ecc71")}

                <line
                    x1={cx}
                    y1={cy}
                    x2={needleX}
                    y2={needleY}
                    stroke="#f5f7fa"
                    strokeWidth={radius * 0.04}
                    strokeLinecap="round"
                />

                <circle cx={cx} cy={cy} r={radius * 0.06} fill="#f5f7fa" />

                <text
                    x={cx}
                    y={cy - radius - 20}
                    textAnchor="middle"
                    fontSize={radius * 0.18}
                    fontWeight="bold"
                    fill="#f5f8ff"
                    stroke="rgba(8,12,28,0.9)"
                    strokeWidth={1.25}
                    paintOrder="stroke"
                    style={{ paintOrder: 'stroke fill' }}
                >
                    {`SRI: ${sriPercent.toFixed(2)}%`}
                </text>

                <text
                    x={cx}
                    y={Math.min(cy + radius * 0.15 + 10, height - 8)}
                    textAnchor="middle"
                    fontSize={radius * 0.16}
                    fill="#e8eef5"
                    fontWeight="bold"
                    stroke="rgba(8,12,28,0.9)"
                    strokeWidth={1.25}
                    paintOrder="stroke"
                    style={{ paintOrder: 'stroke fill' }}
                >
                    {instruction}
                </text>
            </svg>
        </div>
    );
};

function computeEndDate(start) {
    const d = new Date(start);
    d.setDate(d.getDate() + 29);
    return d.toISOString().slice(0, 10).replace(/-/g, "");
}

function InfoPanel({
    panel,
    selectedPanel,
    startDate,
    onBillDifferenceComputed
}) {
    const [panelData, setPanelData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [selectedDayIndex, setSelectedDayIndex] = useState(null);
    const abortRef = useRef(null);
    const debounceRef = useRef(null);

    const apiStart = startDate.replace(/-/g, "");
    const apiEnd = computeEndDate(startDate);

    // SRI comes from /api/panel/data (no separate /sri round-trip).
    const sriData = useMemo(() => {
        if (!panelData?.length) return [];
        return panelData
            .map((d) => ({ date: d.date, SRI: d.SRI ?? d.sri ?? null }))
            .filter((d) => d.SRI != null);
    }, [panelData]);

    useEffect(() => {
        if (!selectedPanel) return;
        if (panel && panel.inferenceCapable === false) {
            setPanelData(null);
            setError(null);
            setLoading(false);
            onBillDifferenceComputed?.(null);
            return;
        }

        if (debounceRef.current) clearTimeout(debounceRef.current);
        if (abortRef.current) abortRef.current.abort();

        debounceRef.current = setTimeout(() => {
            const controller = new AbortController();
            abortRef.current = controller;

            async function fetchPanelData() {
                setLoading(true);
                setError(null);
                setSelectedDayIndex(null);
                setPanelData(null);

                try {
                    const response = await fetch(
                        `${API_BASE}/api/panel/data?site=${encodeURIComponent(selectedPanel)}&start_date=${apiStart}&end_date=${apiEnd}`,
                        { signal: controller.signal }
                    );

                    if (!response.ok) {
                        let detail = response.statusText;
                        try {
                            const body = await response.json();
                            detail = body.detail || detail;
                        } catch (_) { /* ignore */ }
                        throw new Error(
                            typeof detail === 'string'
                                ? detail
                                : `Failed to fetch data for ${selectedPanel}`
                        );
                    }

                    const data = await response.json();

                    if (!Array.isArray(data)) {
                        throw new Error("Unexpected backend response format — expected an array of daily weather data.");
                    }

                    if (controller.signal.aborted) return;
                    setPanelData(data);
                } catch (err) {
                    if (err.name === 'AbortError') return;
                    console.error(err);
                    setError(err.message);
                    onBillDifferenceComputed?.(null);
                } finally {
                    if (!controller.signal.aborted) setLoading(false);
                }
            }

            fetchPanelData();
        }, 150);

        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
            if (abortRef.current) abortRef.current.abort();
        };
    }, [selectedPanel, startDate, panel?.inferenceCapable, apiStart, apiEnd, onBillDifferenceComputed]);

    const billSummary = useMemo(() => {
        if (!Array.isArray(panelData) || panelData.length === 0) return null;

        const totals = panelData.reduce(
            (sum, day) => ({
                baselineMwh: sum.baselineMwh + (Number(day.baseline) || 0),
                wildfireMwh: sum.wildfireMwh + (Number(day.lstm_pred) || 0),
            }),
            { baselineMwh: 0, wildfireMwh: 0 }
        );
        const dollarsPerMwh = ELECTRICITY_RATE_PER_KWH * KWH_PER_MWH;
        const baselineBill = totals.baselineMwh * dollarsPerMwh;
        const wildfireBill = totals.wildfireMwh * dollarsPerMwh;

        return {
            ...totals,
            baselineBill,
            wildfireBill,
            difference: Math.max(0, baselineBill - wildfireBill),
            days: panelData.length,
        };
    }, [panelData]);

    useEffect(() => {
        const difference = billSummary?.difference;
        onBillDifferenceComputed?.(
            Number.isFinite(difference) && difference > 0 ? difference : null
        );
    }, [billSummary, onBillDifferenceComputed]);

    useEffect(() => {
        if (panelData && panelData.length > 0 && selectedDayIndex === null) {
            setSelectedDayIndex(0);
        }
    }, [panelData, selectedDayIndex]);

    if (!selectedPanel) {
        return <div className="info-panel">Click a solar panel on the map.</div>;
    }

    if (panel && panel.inferenceCapable === false) {
        return (
            <div className="info-panel info-panel--map-only">
                <h3>{panel.name}</h3>
                <div className="fw-callout-warn">
                    Map / inventory only — no PM2.5 source could be resolved for this
                    plant (no nearby EPA monitor and Open-Meteo unavailable).
                </div>
                <div className="site-meta-grid">
                    <div><span>State</span><b>{panel.state || '—'}</b></div>
                    <div><span>County</span><b>{panel.county || '—'}</b></div>
                    <div><span>Capacity</span><b>{panel.capacity || '—'}</b></div>
                    <div><span>Year online</span><b>{panel.yearOnline || '—'}</b></div>
                    <div><span>Source</span><b>USGS USPVDB</b></div>
                    <div><span>Case ID</span><b>{panel.number || '—'}</b></div>
                    <div><span>Lat / Lon</span><b>{panel.latitude?.toFixed?.(4)}, {panel.longitude?.toFixed?.(4)}</b></div>
                </div>
            </div>
        );
    }

    if (loading && !panelData) {
        return (
            <div className="info-panel">
                <h3>{panel?.name || `Site ${selectedPanel}`}</h3>
                <div className="fw-loading-inline">
                    Loading forecast data… map stays interactive.
                </div>
            </div>
        );
    }

    if (error) {
        return <div className="info-panel">⚠️ {error}</div>;
    }

    if (!panelData || panelData.length === 0) {
        return <div className="info-panel">No weather data available for this date range.</div>;
    }

    const aqNote =
        panel?.note && panel?.pm25Source && panel.pm25Source !== 'epa'
            ? panel.note
            : null;

    return (
        <div className="info-panel">
            <h3>Site: {panel?.name}, {panel?.county} County</h3>
            {loading && (
                <div className="fw-loading-inline">Refreshing forecast…</div>
            )}
            {aqNote && (
                <div className="fw-callout-aq" title={aqNote}>
                    {aqNote}
                </div>
            )}

            {billSummary && (
                <section className="bill-summary" aria-labelledby="bill-summary-title">
                    <div className="bill-summary__heading">
                        <div>
                            <span className="bill-summary__eyebrow">
                                Selected monthly period · {billSummary.days} days
                            </span>
                            <h4 id="bill-summary-title">Estimated Monthly Electricity Bill</h4>
                        </div>
                        <span className="bill-summary__rate">
                            ${ELECTRICITY_RATE_PER_KWH.toFixed(2)}/kWh assumed rate
                        </span>
                    </div>

                    <div className="bill-summary__values">
                        <div className="bill-summary__scenario bill-summary__scenario--baseline">
                            <span>Baseline · no wildfire</span>
                            <strong>
                                {billSummary.baselineBill.toLocaleString(undefined, {
                                    style: 'currency',
                                    currency: 'USD',
                                })}
                            </strong>
                            <small>{billSummary.baselineMwh.toFixed(1)} MWh</small>
                        </div>

                        <div className="bill-summary__scenario bill-summary__scenario--wildfire">
                            <span>Wildfire-affected</span>
                            <strong>
                                {billSummary.wildfireBill.toLocaleString(undefined, {
                                    style: 'currency',
                                    currency: 'USD',
                                })}
                            </strong>
                            <small>{billSummary.wildfireMwh.toFixed(1)} MWh</small>
                        </div>

                        <div className="bill-summary__difference">
                            <span>Cumulative bill difference</span>
                            <strong>
                                {billSummary.difference.toLocaleString(undefined, {
                                    style: 'currency',
                                    currency: 'USD',
                                })}
                            </strong>
                            <small>baseline minus wildfire-affected</small>
                        </div>
                    </div>
                </section>
            )}

            <div className="info-content">

                {/* LEFT SIDE — BAR CHART */}
                <div className="left-side">
                    <BarChart data={panelData} />
                </div>

                {/* RIGHT SIDE — SPARKLINE + GAUGE */}
                <div className="right-side">

                    {/* Sparkline (top) */}
                    <div className="sri-trend-container">
                        <SRITrend
                            sriData={sriData}
                            selectedDayIndex={selectedDayIndex}
                            onSelectDay={setSelectedDayIndex}
                        />
                    </div>

                    {/* Gauge (bottom) */}
                    <div className="sri-gauge-container">
                        <SRIGauge
                            value={
                                sriData && selectedDayIndex != null
                                    ? sriData[selectedDayIndex]?.SRI
                                    : null
                            }
                        />
                    </div>
                </div>

            </div>
        </div>
    );
}

export default InfoPanel;