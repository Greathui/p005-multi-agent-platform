// assets/charts.js — P005 软件开发经验总结图表
(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var bad = style.getPropertyValue('--bad').trim();

  var chartEl = document.getElementById('chart-bug-distribution');
  if (!chartEl || typeof echarts === 'undefined') return;

  var chart = echarts.init(chartEl, null, { renderer: 'svg' });

  var layers = ['API 层测试', '前端 UI 测试', '端到端测试', 'LLM 长任务测试'];
  var caseCounts = [32, 6, 27, 2];
  var bugCounts = [0, 0, 0, 2];

  chart.setOption({
    backgroundColor: 'transparent',
    animation: false,
    grid: {
      left: 60,
      right: 30,
      top: 60,
      bottom: 60
    },
    legend: {
      data: ['测试用例数', '发现严重 bug 数'],
      top: 10,
      textStyle: { color: ink, fontSize: 12 },
      itemWidth: 14,
      itemHeight: 10
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      textStyle: { fontSize: 12 },
      formatter: function (params) {
        var idx = params[0].dataIndex;
        var html = '<strong>' + layers[idx] + '</strong><br/>';
        html += '测试用例数：' + caseCounts[idx] + '<br/>';
        html += '发现严重 bug 数：' + bugCounts[idx];
        if (idx === 3) {
          html += '<br/><span style="color:' + bad + ';">仅 2 个用例就发现了前 65 个用例漏掉的 2 个严重 bug</span>';
        }
        return html;
      }
    },
    xAxis: {
      type: 'category',
      data: layers,
      axisLabel: {
        color: ink,
        fontSize: 11,
        interval: 0,
        formatter: function (value, index) {
          return value + '\n(' + caseCounts[index] + ' 用例)';
        }
      },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    yAxis: [
      {
        type: 'value',
        name: '用例数',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        splitLine: { lineStyle: { color: rule, type: 'dashed' } },
        axisLine: { show: false }
      },
      {
        type: 'value',
        name: 'bug 数',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11, formatter: '{value}' },
        splitLine: { show: false },
        axisLine: { show: false },
        max: 3
      }
    ],
    series: [
      {
        name: '测试用例数',
        type: 'bar',
        data: caseCounts,
        itemStyle: {
          color: function (params) {
            return params.dataIndex === 3 ? accent2 : accent;
          },
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '38%',
        label: {
          show: true,
          position: 'top',
          color: ink,
          fontSize: 12,
          fontWeight: 600
        }
      },
      {
        name: '发现严重 bug 数',
        type: 'bar',
        yAxisIndex: 1,
        data: bugCounts,
        itemStyle: {
          color: bad,
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '38%',
        label: {
          show: true,
          position: 'top',
          color: bad,
          fontSize: 12,
          fontWeight: 700,
          formatter: function (params) {
            return params.value === 0 ? '' : params.value + ' 个';
          }
        }
      }
    ]
  });

  window.addEventListener('resize', function () {
    chart.resize();
  });
})();
