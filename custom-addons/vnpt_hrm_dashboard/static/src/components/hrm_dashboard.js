/** @odoo-module */

import { registry } from "@web/core/registry"

import { loadJS } from "@web/core/assets"
import { useService } from "@web/core/utils/hooks"
import {CandleChartRenderer} from "./chart_renderer/candle_chart_renderer";
const { Component, onWillStart, useRef, onMounted, useState } = owl
const { DateTime } = luxon;

export class OwlHrmDashboard extends Component {
    setup(){
        this.state = useState({
            employee: false,
            birthdayEmpls: false,
            salaryIncreaseContracts: [],
            nearlyExpiredContracts: [],
            alerts: {
                expiredContracts: 0,
                nearlyExpiredContracts: 0,
                salaryIncrease: 0
            },
        })
        this.orm = useService("orm")
        this.actionService = useService("action")

        onWillStart(async ()=>{
            await this.getCurrentEmployeeData();
            await this.getEmployeeBirthday();
            await this.getAlertInformation();
        })
    }

    async getCurrentEmployeeData() {
        this.state.employee = await this.orm.call("hr.employee", 'get_current_employee_data', [0, this.env.services.user.userId]);

        this.isHrManager = await this.env.services.user.hasGroup('hr.group_hr_user');
        this.isContractManager = await this.env.services.user.hasGroup('hr_contract.group_hr_contract_employee_manager');
        this.isInsuranceManager = await this.env.services.user.hasGroup('vnpt_hrm.group_hr_insurance_user');
        this.isAttendanceManager = await this.env.services.user.hasGroup('hr_attendance.group_hr_attendance_manager');
        this.isHolidaysManager = await this.env.services.user.hasGroup('hr_holidays.group_hr_holidays_user');
        this.isRecruitmentManager = await this.env.services.user.hasGroup('hr_recruitment.group_hr_recruitment_interviewer');
        this.isPayrollManager = await this.env.services.user.hasGroup('hr_payroll.group_hr_payroll_employee_manager');
    }

    async getAlertInformation() {
        const alerts = await this.orm.call("hr.employee", "get_manager_alerts", [0]);
        this.state.alerts = alerts.counts;
        this.state.salaryIncreaseContracts = alerts.salaryIncrease;
        this.state.nearlyExpiredContracts = alerts.nearlyExpiredContracts;
    }

    async getEmployeeBirthday() {
        this.state.birthdayEmpls = await this.orm.call("hr.employee", 'get_employee_birthdays', [0]);
    }

    openContract() {
        this.actionService.doAction("hr_contract.action_hr_contract");
    }

    openSalaryIncreaseContracts() {
        this.actionService.doAction({
            name: "Hợp đồng cảnh báo tăng lương",
            type: "ir.actions.act_window",
            res_model: "hr.contract",
            views: [[false, 'list'], [false, 'form']],
            domain: [["id", "in", this.state.salaryIncreaseContracts]],
            target: 'current',
        });
    }

    openNearlyExpiredContracts() {
        this.actionService.doAction({
            name: "Hợp đồng gần hết hạn",
            type: "ir.actions.act_window",
            res_model: "hr.contract",
            views: [[false, 'list'], [false, 'form']],
            domain: [["id", "in", this.state.nearlyExpiredContracts]],
            target: 'current',
        });
    }

    async openPersonalProfile() {
        try {
            // Call the Python method via RPC
            const action = await this.orm.call(
                "hr.employee",  // Model name
                "action_open_current_employee_info",  // Method name
                [this.state.employee.id, this.state.employee.name]  // Arguments
            );

            // Execute the action
            this.actionService.doAction(action);
        } catch (error) {
            console.error("Không thể lấy thông tin :", error);
        }
    }
}

OwlHrmDashboard.template = "owl.OwlHrmDashboard"
OwlHrmDashboard.components = { CandleChartRenderer }

registry.category("actions").add("owl.vnpt_hrm_dashboard", OwlHrmDashboard)