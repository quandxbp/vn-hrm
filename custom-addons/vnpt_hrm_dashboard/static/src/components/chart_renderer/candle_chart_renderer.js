/** @odoo-module */

import { registry } from "@web/core/registry"
import { loadJS } from "@web/core/assets"
const { Component, onWillStart, useRef, onMounted } = owl

export class CandleChartRenderer extends Component {
    setup(){
        this.chartRef = useRef("chart")
        onWillStart(async ()=>{
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js")
            await loadJS("https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1")
            await loadJS("/tradingview_dashboard/static/lib/chartjs-chart-financial.js");
        })

        onMounted(()=>this.renderChart())
    }

    renderChart() {
        try {
            let dataString = this.props.data.trim();

            dataString = dataString.replace(/'/g, '"');
            dataString = dataString.replace(/False/g, 'false');
            dataString = dataString.replace(/True/g, 'true');
            dataString = dataString.replace(/[\n\t]/g, '');

            let data = JSON.parse(dataString);

            let barData = data.map(item => {
                return {
                    x: item.time,
                    o: item.open,
                    h: item.max,
                    l: item.min,
                    c: item.close
                };
            });

            new Chart(this.chartRef.el,
                {
                    type: 'candlestick',
                    data: {
                        datasets: [{
                            label: 'Candle',
                            data: barData,
                            yAxisID: 'y',
                        }, {
                            label: 'MACD',
                            type: 'line',
                            data: data.map(item => {
                                return {
                                    x: item.time,
                                    y: item.macd,
                                };
                            }),
                            yAxisID: 'y1',
                        }, {
                            label: 'Signal',
                            type: 'line',
                            data: data.map(item => {
                                return {
                                    x: item.time,
                                    y: item.signal,
                                };
                            }),
                            yAxisID: 'y1',
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                // Ensure this axis does not collide with the first
                                grid: {
                                    drawOnChartArea: false, // only want the grid lines for one axis to show up
                                },
                            },
                        },
                        plugins: {
                            legend: {
                                position: 'bottom',
                            },
                            title: {
                                display: true,
                                text: this.props.title,
                                position: 'bottom',
                            }
                        }
                    },
                }
            );
        } catch (error) {
            console.error(this.props.title, this.props.data);
        }
    }

}

CandleChartRenderer.template = "owl.CandleChartRenderer"