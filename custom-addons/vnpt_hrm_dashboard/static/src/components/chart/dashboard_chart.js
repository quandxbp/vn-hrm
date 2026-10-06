/** @odoo-module */

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";

/**
 * Biểu đồ dùng Chart.js có sẵn trong Odoo (bundle web.chartjs_lib).
 * Màu sắc lấy từ CSS variables của dashboard nên tự đổi theo theme / dark mode.
 */
export class DashboardChart extends Component {
    static template = "vnpt_hrm_dashboard.DashboardChart";
    static props = {
        type: { type: String }, // "bar" | "hbar" | "doughnut"
        labels: { type: Array },
        values: { type: Array },
        tones: { type: Array, optional: true }, // primary | success | info | warning | danger | muted
        datasetLabel: { type: String, optional: true },
    };

    setup() {
        this.canvas = useRef("canvas");
        this.chart = null;
        onMounted(() => this.renderChart());
        onWillUnmount(() => this.chart?.destroy());
    }

    renderChart() {
        const style = getComputedStyle(this.canvas.el);
        const css = (name) => style.getPropertyValue(name).trim();
        const muted = css("--vd-muted");
        const border = css("--vd-border");

        const tones = this.props.tones?.length ? this.props.tones : ["primary"];
        const colors = this.props.values.map((_, i) => css(`--vd-${tones[i % tones.length]}`));

        const isDoughnut = this.props.type === "doughnut";
        const horizontal = this.props.type === "hbar";

        const valueAxis = {
            beginAtZero: true,
            ticks: { color: muted, precision: 0 },
            grid: { color: border },
            border: { display: false },
        };
        const labelAxis = {
            ticks: { color: muted },
            grid: { display: false },
            border: { display: false },
        };

        this.chart = new Chart(this.canvas.el, {
            type: isDoughnut ? "doughnut" : "bar",
            data: {
                labels: this.props.labels,
                datasets: [
                    {
                        label: this.props.datasetLabel || "",
                        data: this.props.values,
                        backgroundColor: colors,
                        borderRadius: isDoughnut ? 0 : 6,
                        maxBarThickness: 34,
                        borderWidth: isDoughnut ? 3 : 0,
                        borderColor: css("--vd-card"),
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: horizontal ? "y" : "x",
                cutout: isDoughnut ? "68%" : undefined,
                plugins: {
                    legend: isDoughnut
                        ? {
                              position: "bottom",
                              labels: { color: muted, usePointStyle: true, boxWidth: 8, padding: 14 },
                          }
                        : { display: false },
                },
                scales: isDoughnut
                    ? {}
                    : horizontal
                    ? { x: valueAxis, y: labelAxis }
                    : { x: labelAxis, y: valueAxis },
            },
        });
    }
}
