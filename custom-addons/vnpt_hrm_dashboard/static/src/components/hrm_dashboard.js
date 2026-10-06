/** @odoo-module */

import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { DashboardChart } from "./chart/dashboard_chart";

const { DateTime } = luxon;

const CONTRACT_STATE_TONES = { draft: "info", open: "success", close: "muted" };

export class OwlHrmDashboard extends Component {
    static template = "vnpt_hrm_dashboard.Dashboard";
    static components = { DashboardChart };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.perms = {};
        this.state = useState({
            employee: {},
            birthdayEmpls: [],
            stats: null,
            alerts: {
                expiredContracts: 0,
                nearlyExpiredContracts: 0,
                salaryIncrease: 0,
            },
            salaryIncreaseContracts: [],
            nearlyExpiredContracts: [],
        });

        onWillStart(() => this.loadData());
    }

    async loadData() {
        const user = this.env.services.user;
        const [employee, isHrManager, isContractManager, isInsuranceManager, isRecruitmentManager] =
            await Promise.all([
                this.orm.call("hr.employee", "get_current_employee_data", [0, user.userId]),
                user.hasGroup("hr.group_hr_user"),
                user.hasGroup("hr_contract.group_hr_contract_employee_manager"),
                user.hasGroup("vnpt_hrm.group_hr_insurance_user"),
                user.hasGroup("hr_recruitment.group_hr_recruitment_interviewer"),
            ]);
        this.state.employee = employee;
        this.perms = { isHrManager, isContractManager, isInsuranceManager, isRecruitmentManager };

        await Promise.all([
            this.loadBirthdays(),
            isContractManager ? this.loadAlerts() : null,
            isHrManager ? this.loadStats() : null,
        ]);
    }

    async loadBirthdays() {
        this.state.birthdayEmpls = (await this.orm.call("hr.employee", "get_employee_birthdays", [0])) || [];
    }

    async loadAlerts() {
        const alerts = await this.orm.call("hr.employee", "get_manager_alerts", [0]);
        this.state.alerts = alerts.counts;
        this.state.salaryIncreaseContracts = alerts.salaryIncrease;
        this.state.nearlyExpiredContracts = alerts.nearlyExpiredContracts;
    }

    async loadStats() {
        const [stats] = await Promise.all([
            this.orm.call("hr.employee", "get_dashboard_stats", []),
            loadBundle("web.chartjs_lib"),
        ]);
        this.state.stats = stats && stats.total !== undefined ? stats : null;
    }

    // ---- Hiển thị -----------------------------------------------------

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
        const name = this.state.employee.name;
        return name ? name.trim().split(/\s+/).pop() : "";
    }

    get todayLabel() {
        return DateTime.now().setLocale("vi").toFormat("cccc, dd/MM/yyyy");
    }

    get totalAlerts() {
        const { expiredContracts, nearlyExpiredContracts, salaryIncrease } = this.state.alerts;
        return expiredContracts + nearlyExpiredContracts + salaryIncrease;
    }

    get quickLinks() {
        const { isHrManager, isContractManager, isInsuranceManager, isRecruitmentManager } = this.perms;
        const links = [];
        if (this.state.employee.id) {
            links.push({
                key: "profile",
                label: "Hồ sơ cá nhân",
                icon: "/vnpt_hrm/static/description/icon_ho_so_nhan_su.png",
                onClick: () => this.openPersonalProfile(),
            });
        }
        links.push(
            isHrManager
                ? {
                      key: "employees",
                      label: "Nhân sự",
                      icon: "/hr/static/description/icon.png",
                      onClick: () => this.actionService.doAction("hr.open_view_employee_list_my"),
                  }
                : {
                      key: "directory",
                      label: "Danh bạ nhân sự",
                      icon: "/hr/static/description/icon.png",
                      onClick: () => this.actionService.doAction("hr.hr_employee_public_action"),
                  },
            {
                key: "leave",
                label: "Nghỉ phép",
                icon: "/hr_holidays/static/description/icon.png",
                onClick: () => this.actionService.doAction("hr_holidays.hr_leave_action_new_request"),
            },
            {
                key: "attendance",
                label: "Chấm công",
                icon: "/hr_attendance/static/description/icon.png",
                onClick: () => this.actionService.doAction("hr_attendance.hr_attendance_action"),
            }
        );
        if (isContractManager) {
            links.push({
                key: "contract",
                label: "Hợp đồng",
                icon: "/vnpt_hrm/static/description/icon_contract.png",
                onClick: () => this.openContract(),
            });
        }
        if (isInsuranceManager) {
            links.push({
                key: "insurance",
                label: "Bảo hiểm",
                icon: "/vnpt_hrm/static/description/icon_bao_hiem.png",
                onClick: () => this.actionService.doAction("vnpt_hrm.hr_insurance_action"),
            });
        }
        if (isRecruitmentManager) {
            links.push({
                key: "recruitment",
                label: "Tuyển dụng",
                icon: "/hr_recruitment/static/description/icon.png",
                onClick: () => this.actionService.doAction("hr_recruitment.action_hr_job"),
            });
        }
        return links;
    }

    get kpis() {
        const stats = this.state.stats;
        if (!stats) {
            return [];
        }
        const kpis = [
            {
                key: "total",
                label: "Tổng nhân sự",
                value: stats.total,
                icon: "fa-users",
                tone: "primary",
                onClick: () => this.actionService.doAction("hr.open_view_employee_list_my"),
            },
            {
                key: "new",
                label: "Tuyển mới tháng này",
                value: stats.newThisMonth,
                icon: "fa-user-plus",
                tone: "success",
            },
            {
                key: "leave",
                label: "Đang nghỉ phép hôm nay",
                value: stats.onLeaveToday,
                icon: "fa-plane",
                tone: "info",
            },
        ];
        if (this.perms.isContractManager) {
            kpis.push({
                key: "alerts",
                label: "Cảnh báo cần xử lý",
                value: this.totalAlerts,
                icon: "fa-bell",
                tone: this.totalAlerts ? "warning" : "success",
            });
        }
        return kpis;
    }

    get alertItems() {
        const alerts = this.state.alerts;
        return [
            {
                key: "nearly",
                label: "Hợp đồng gần hết hạn",
                count: alerts.nearlyExpiredContracts,
                icon: "fa-hourglass-half",
                tone: "warning",
                onClick: () => this.openNearlyExpiredContracts(),
            },
            {
                key: "expired",
                label: "Hợp đồng hết hạn",
                count: alerts.expiredContracts,
                icon: "fa-file-text-o",
                tone: "danger",
                onClick: () => this.openExpiredContracts(),
            },
            {
                key: "salary",
                label: "Cảnh báo nâng lương",
                count: alerts.salaryIncrease,
                icon: "fa-line-chart",
                tone: "info",
                onClick: () => this.openSalaryIncreaseContracts(),
            },
        ];
    }

    get hiresChart() {
        const rows = this.state.stats?.hiresByMonth || [];
        return { labels: rows.map((r) => r.label), values: rows.map((r) => r.count) };
    }

    get departmentChart() {
        const rows = this.state.stats?.byDepartment || [];
        return { labels: rows.map((r) => r.label), values: rows.map((r) => r.count) };
    }

    get contractChart() {
        const rows = this.state.stats?.contractsByState || [];
        return {
            labels: rows.map((r) => r.label),
            values: rows.map((r) => r.count),
            tones: rows.map((r) => CONTRACT_STATE_TONES[r.key] || "muted"),
        };
    }

    hasData(chart) {
        return chart.values.some((value) => value > 0);
    }

    // ---- Hành động ----------------------------------------------------

    openContract() {
        this.actionService.doAction("hr_contract.action_hr_contract");
    }

    openExpiredContracts() {
        this.actionService.doAction("vnpt_hrm.action_close_hr_contract");
    }

    openSalaryIncreaseContracts() {
        this.actionService.doAction({
            name: "Hợp đồng cảnh báo tăng lương",
            type: "ir.actions.act_window",
            res_model: "hr.contract",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", this.state.salaryIncreaseContracts]],
            target: "current",
        });
    }

    openNearlyExpiredContracts() {
        this.actionService.doAction({
            name: "Hợp đồng gần hết hạn",
            type: "ir.actions.act_window",
            res_model: "hr.contract",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", this.state.nearlyExpiredContracts]],
            target: "current",
        });
    }

    async openPersonalProfile() {
        try {
            const action = await this.orm.call("hr.employee", "action_open_current_employee_info", [
                this.state.employee.id,
                this.state.employee.name,
            ]);
            this.actionService.doAction(action);
        } catch (error) {
            console.error("Không thể lấy thông tin :", error);
        }
    }
}

registry.category("actions").add("owl.vnpt_hrm_dashboard", OwlHrmDashboard);
