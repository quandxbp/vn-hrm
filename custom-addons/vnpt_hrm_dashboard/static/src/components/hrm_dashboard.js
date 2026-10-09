/** @odoo-module */

import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { DashboardChart } from "./chart/dashboard_chart";

const { DateTime } = luxon;

const PRIORITY_LABELS = {
    red_now: "Đỏ - liên hệ ngay",
    red: "Đỏ",
    yellow: "Vàng",
};
const PRIORITY_TONES = { red_now: "danger", red: "danger", yellow: "warning" };
const FEE_LABELS = { out: "Hết học phí", low: "Gần hết học phí" };
const money = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

export class OwlGvnnDashboard extends Component {
    static template = "vnpt_hrm_dashboard.Dashboard";
    static components = { DashboardChart };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({ data: null });
        onWillStart(async () => {
            const [data] = await Promise.all([
                this.orm.call("edu.dashboard", "get_data", []),
                loadBundle("web.chartjs_lib"),
            ]);
            this.state.data = data;
        });
    }

    // ---- Hiển thị -----------------------------------------------------

    money(value) {
        return money.format(value || 0) + " đ";
    }

    priorityLabel(key) {
        return PRIORITY_LABELS[key] || key;
    }

    priorityTone(key) {
        return PRIORITY_TONES[key] || "muted";
    }

    feeLabel(key) {
        return FEE_LABELS[key] || "";
    }

    get greeting() {
        const hour = new Date().getHours();
        if (hour < 11) {
            return "Chào buổi sáng";
        }
        if (hour < 13) {
            return "Chào buổi trưa";
        }
        return hour < 18 ? "Chào buổi chiều" : "Chào buổi tối";
    }

    get firstName() {
        const name = this.state.data?.user_name;
        return name ? name.trim().split(/\s+/).pop() : "";
    }

    get todayLabel() {
        return DateTime.now().setLocale("vi").toFormat("cccc, dd/MM/yyyy");
    }

    get kpis() {
        const { data } = this.state;
        const kpis = [
            {
                key: "studying",
                label: "Học viên đang học",
                value: data.studying,
                icon: "fa-graduation-cap",
                tone: "primary",
                onClick: () => this.openAction("edu_gvnn.action_edu_student"),
            },
        ];
        if (data.finance) {
            const f = data.finance;
            kpis.push(
                {
                    key: "income",
                    label: `Tiền thu năm ${f.year}`,
                    value: this.money(f.income),
                    icon: "fa-money",
                    tone: "success",
                },
                {
                    key: "cost",
                    label: `Tổng chi năm ${f.year}`,
                    value: this.money(f.cost),
                    icon: "fa-credit-card",
                    tone: "warning",
                },
                {
                    key: "flow",
                    label: "Dòng tiền sau chi",
                    value: this.money(f.cash_flow),
                    icon: "fa-line-chart",
                    tone: f.cash_flow >= 0 ? "info" : "danger",
                },
                {
                    key: "balance",
                    label: "Số dư học phí",
                    value: this.money(f.balance),
                    icon: "fa-bank",
                    tone: "primary",
                }
            );
        }
        return kpis;
    }

    get alertItems() {
        const a = this.state.data.alerts;
        const item = (key, label, count, icon, tone, filter) => ({
            key,
            label,
            count,
            icon,
            tone,
            onClick: () => this.openAlerts(label, filter),
        });
        return [
            item("red", "Ưu tiên đỏ", a.red, "fa-exclamation-circle", "danger", [["priority", "in", ["red_now", "red"]]]),
            item("absent", "Nghỉ trong tuần", a.absent, "fa-user-times", "warning", [["absent", "=", true]]),
            item("absent_3w", "Nghỉ nhiều tuần liên tiếp", a.absent_3w, "fa-calendar-times-o", "danger", [["absent_3w", "=", true]]),
            item("fee_out", "Hết học phí", a.fee_out, "fa-battery-empty", "danger", [["fee_warning", "=", "out"]]),
            item("fee_low", "Gần hết học phí", a.fee_low, "fa-battery-quarter", "warning", [["fee_warning", "=", "low"]]),
            item("suggest_stop", "Đề xuất ngưng học", a.suggest_stop, "fa-stop-circle-o", "info", [["suggest_stop", "=", true]]),
        ];
    }

    get quickLinks() {
        const links = [
            { key: "session", label: "Buổi học", icon: "fa-calendar-check-o", xmlid: "edu_gvnn.action_edu_session" },
            { key: "student", label: "Học viên", icon: "fa-users", xmlid: "edu_gvnn.action_edu_student" },
            { key: "payment", label: "Thu học phí", icon: "fa-money", xmlid: "edu_gvnn.action_edu_tuition_payment" },
            { key: "alert", label: "Cảnh báo tuần", icon: "fa-bell", xmlid: "edu_gvnn.action_edu_week_alert_wizard" },
            { key: "export", label: "Xuất điểm danh", icon: "fa-file-excel-o", xmlid: "edu_gvnn.action_edu_export_week_wizard" },
        ];
        if (this.state.data.is_manager) {
            links.push(
                { key: "payroll", label: "Kỳ lương", icon: "fa-calculator", xmlid: "edu_gvnn.action_edu_payroll_period" },
                { key: "finance", label: "Tài chính", icon: "fa-bar-chart", xmlid: "edu_gvnn.action_edu_report_finance" }
            );
        }
        return links;
    }

    get monthChart() {
        const months = this.state.data.finance?.months || [];
        return {
            labels: months.map((m) => m.label),
            datasets: [
                { label: "Tiền thu", values: months.map((m) => m.income), tone: "primary" },
                { label: "Tổng chi", values: months.map((m) => m.cost), tone: "warning" },
                { label: "Dòng tiền", values: months.map((m) => m.flow), tone: "success" },
            ],
        };
    }

    get hasMonthData() {
        return this.monthChart.datasets.some((ds) => ds.values.some((v) => v));
    }

    get yearChart() {
        const years = this.state.data.finance?.years || [];
        return {
            labels: years.map((y) => y.label),
            datasets: [
                { label: "Tiền thu", values: years.map((y) => y.income), tone: "primary" },
                { label: "Tổng chi", values: years.map((y) => y.cost), tone: "warning" },
                { label: "Dòng tiền", values: years.map((y) => y.flow), tone: "success" },
            ],
        };
    }

    get hasYearData() {
        return this.yearChart.datasets.some((ds) => ds.values.some((v) => v));
    }

    get alertChart() {
        const a = this.state.data.alerts;
        const rows = [
            ["Nghỉ trong tuần", a.absent, "warning"],
            ["Nghỉ nhiều tuần", a.absent_3w, "danger"],
            ["Hết học phí", a.fee_out, "danger"],
            ["Gần hết học phí", a.fee_low, "warning"],
            ["Đề xuất ngưng học", a.suggest_stop, "info"],
            ["Buổi có cảnh báo", a.session_warnings, "muted"],
        ];
        return {
            labels: rows.map((r) => r[0]),
            values: rows.map((r) => r[1]),
            tones: rows.map((r) => r[2]),
            hasData: rows.some((r) => r[1]),
        };
    }

    // ---- Hành động ----------------------------------------------------

    openAction(xmlid) {
        this.actionService.doAction(xmlid);
    }

    openAlerts(name, filter) {
        const week = this.state.data.week;
        this.actionService.doAction({
            name: `${name} - ${week.name}`,
            type: "ir.actions.act_window",
            res_model: "edu.week.alert",
            views: [[false, "list"]],
            domain: [["week_id", "=", week.id], ...filter],
            target: "current",
        });
    }

    openSessionWarnings() {
        const week = this.state.data.week;
        this.actionService.doAction({
            name: `Buổi có cảnh báo - ${week.name}`,
            type: "ir.actions.act_window",
            res_model: "edu.session",
            views: [[false, "list"], [false, "form"]],
            domain: [["week_id", "=", week.id], ["state", "=", "done"], ["warning", "!=", "ok"]],
            target: "current",
        });
    }
}

registry.category("actions").add("owl.vnpt_hrm_dashboard", OwlGvnnDashboard);
